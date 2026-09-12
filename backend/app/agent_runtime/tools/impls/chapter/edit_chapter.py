import json
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.tools.base import AgentTool
from app.core.editor_content_limits import EditorContentLimitError, validate_editor_content
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    images_by_id,
    record_agent_activity_for_change,
    record_chapter_diffs,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.chapter.diff_preview import (
    build_chapter_diff_preview,
    build_edit_chapter_tool_result_preview,
    chapter_preview_from_object,
)
from app.agent_runtime.tools.impls.chapter.refs import (
    ChapterRef,
    VolumeRef,
    resolve_chapter_from_list,
    resolve_volume_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.agent_runtime.tools.text_match import fuzzy_replace
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo
from app.storage.services.version_control_service import refresh_project_stats


def count_words(text: str) -> int:
    if not text:
        return 0
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    text_without_chinese = re.sub(r"[\u4e00-\u9fff]", " ", text)
    english_words = [w for w in text_without_chinese.split() if w.strip()]
    return len(chinese_chars) + len(english_words)


class EditChapterInput(BaseModel):
    volume_ref: VolumeRef = Field(description="Volume sasaran")
    chapter_ref: ChapterRef = Field(description="Bab sasaran")
    new_title: str | None = Field(
        default=None,
        description=(
            "Judul bab yang baru, opsional; isi hanya bila mengubah judul"
        ),
    )
    old_content: str | None = Field(
        default=None,
        description=(
            "Teks asli yang akan dicari dan diganti; isi hanya bila mengubah isi utama"
        ),
    )
    new_content: str | None = Field(
        default=None,
        description=(
            "Teks baru sebagai pengganti; isi hanya bila mengubah isi utama"
        ),
    )
    replace_all: bool = Field(
        default=False,
        description=(
            "Apakah mengganti seluruh old_content yang cocok; bila diisi false hanya "
            "kecocokan pertama yang diganti"
        ),
    )

    @field_validator("old_content", mode="after")
    @classmethod
    def reject_empty_old_content(cls, v):
        if v is not None and v == "":
            raise ValueError("old_content tidak boleh berupa string kosong")
        return v

    @field_validator("new_content", mode="after")
    @classmethod
    def check_edit_fields(cls, v, info):
        data = info.data
        has_title = data.get("new_title") is not None
        has_content = data.get("old_content") is not None and v is not None
        if not has_title and not has_content:
            raise ValueError(
                "salah satu dari new_title atau old_content/new_content wajib diisi"
            )
        return v


@ToolRegistry.register
class EditChapterTool(AgentTool):
    name: str = "edit_chapter"
    description: str = "Menyunting judul atau isi bab yang ditentukan"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditChapterInput

    async def build_interrupt_preview(self, args: dict[str, Any]) -> dict | None:
        session = self.get_runtime_db_session()
        if session is None:
            return None
        volume_ref = args.get("volume_ref")
        if isinstance(volume_ref, VolumeRef):
            volume_ref = volume_ref.model_dump()
        if not isinstance(volume_ref, dict):
            return None
        chapter_ref = args.get("chapter_ref")
        if isinstance(chapter_ref, ChapterRef):
            chapter_ref = chapter_ref.model_dump()
        if not isinstance(chapter_ref, dict):
            return None
        new_title = args.get("new_title")
        old_content = args.get("old_content")
        new_content = args.get("new_content")
        return await build_edit_chapter_tool_result_preview(
            session,
            self.project_id,
            volume_ref=volume_ref,
            chapter_ref=chapter_ref,
            new_title=new_title if isinstance(new_title, str) else None,
            old_content=old_content if isinstance(old_content, str) else None,
            new_content=new_content if isinstance(new_content, str) else None,
            replace_all=bool(args.get("replace_all")),
        )

    async def _execute(
        self,
        volume_ref: dict,
        chapter_ref: dict,
        new_title: str | None = None,
        old_content: str | None = None,
        new_content: str | None = None,
        replace_all: bool = False,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError(
                "revision saat ini tidak ada, penyuntingan bab tidak dapat dijalankan"
            )
        volume_ref_model = VolumeRef.model_validate(volume_ref)
        ref = ChapterRef.model_validate(chapter_ref)
        session = await create_session()
        try:
            volume = resolve_volume_from_list(
                await volume_repo.list_by_project(session, self.project_id),
                volume_ref_model,
            )
            matched = await chapter_repo.get_by_volume_ref(
                session,
                volume.id,
                ref_type=ref.type,
                ref_value=ref.value,
            )
            match = resolve_chapter_from_list([matched] if matched is not None else [], ref)
            before = images_by_id([match])
            before_match = chapter_preview_from_object(match)
            if new_title is not None:
                match.title = new_title
            if old_content is not None and new_content is not None:
                replace_result = fuzzy_replace(
                    match.content, old_content, new_content, replace_all=replace_all
                )
                if replace_result is None:
                    raise ToolExecutionError(
                        "Teks yang akan diganti tidak ditemukan di dalam isi bab"
                    )
                match.content = replace_result.new_content
                try:
                    validate_editor_content(match.content)
                except EditorContentLimitError as exc:
                    raise ToolExecutionError(str(exc)) from exc
                match.word_count = count_words(match.content)
            match.updated_at = datetime.now(UTC)
            await chapter_repo.update_chapter(session, match)
            chapter_diff = build_chapter_diff_preview(
                before_match,
                chapter_preview_from_object(match),
                path=[volume.title.strip()],
            )
            after = images_by_id([match])
            affected = await record_chapter_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before,
                after=after,
            )
            for chapter_id in affected:
                await record_agent_activity_for_change(
                    session,
                    revision_id=revision_id,
                    task_id=str(self._state.get("task_id") or ""),
                    agent_session_id=self.session_id,
                    before=before.get(chapter_id),
                    after=after.get(chapter_id),
                )
            await refresh_project_stats(session, self.project_id)
            from app.background.jobs import service as background_service
            from app.retrieval.chapter_index import safe_maybe_enqueue_auto_index
            from app.retrieval.index_status import schedule_emit_index_status

            await safe_maybe_enqueue_auto_index(
                session, project_id=self.project_id
            )
            schedule_emit_index_status(session, self.project_id)
            await background_service.commit_and_notify(session)
            return json.dumps(
                {
                    "success": True,
                    "word_count": match.word_count,
                    "metadata": {"chapter_diff": chapter_diff},
                },
                ensure_ascii=False,
            )
        except ToolExecutionError:
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
