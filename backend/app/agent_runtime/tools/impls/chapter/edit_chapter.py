import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    images_by_id,
    record_agent_activity_for_change,
    record_chapter_diffs,
    serialize_chapter,
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
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo
from app.storage.services.version_control_service import refresh_project_stats


def count_words(text: str) -> int:
    if not text:
        return 0
    chinese_chars = re.findall(r"[一-鿿]", text)
    text_without_chinese = re.sub(r"[一-鿿]", " ", text)
    english_words = [w for w in text_without_chinese.split() if w.strip()]
    return len(chinese_chars) + len(english_words)


class EditChapterInput(BaseModel):
    volume_ref: VolumeRef = Field(description="目标章节所在的卷")
    chapter_ref: ChapterRef = Field(description="要编辑的目标章节")
    new_title: str | None = Field(
        default=None,
        description="可选的新章节标题；仅改标题时填写该字段",
    )
    old_content: str | None = Field(
        default=None,
        description="要查找并替换的原始文本；修改正文时必填",
    )
    new_content: str | None = Field(
        default=None,
        description="用于替换 old_content 的新文本；修改正文时必填",
    )
    replace_all: bool = Field(
        default=False,
        description="是否替换命中的全部 old_content；false 时只替换第一处",
    )

    @field_validator("new_content", mode="after")
    @classmethod
    def check_edit_fields(cls, v, info):
        data = info.data
        has_title = data.get("new_title") is not None
        has_content = data.get("old_content") is not None and v is not None
        if not has_title and not has_content:
            raise ValueError("new_title 和 old_content/new_content 必填其中一类")
        return v


@ToolRegistry.register
class EditChapterTool(AgentTool):
    name: str = "edit_chapter"
    description: str = "编辑指定章节的标题或内容。修改内容时使用查找替换模式"
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
            raise ToolExecutionError("缺少当前 revision，无法执行章节编辑")
        volume_ref_model = VolumeRef.model_validate(volume_ref)
        ref = ChapterRef.model_validate(chapter_ref)
        session = await create_session()
        try:
            volume = resolve_volume_from_list(
                await volume_repo.list_by_project(session, self.project_id),
                volume_ref_model,
            )
            chapters = await chapter_repo.list_by_project(session, self.project_id)
            before = images_by_id(chapters)
            volume_chapters = await chapter_repo.list_by_volume(session, volume.id)
            match = resolve_chapter_from_list(volume_chapters, ref)
            before_match = chapter_preview_from_object(match)
            if new_title is not None:
                match.title = new_title
            if old_content is not None and new_content is not None:
                if old_content not in match.content:
                    raise ToolExecutionError("未在章节内容中找到要替换的文本")
                if replace_all:
                    match.content = match.content.replace(old_content, new_content)
                else:
                    match.content = match.content.replace(old_content, new_content, 1)
                match.word_count = count_words(match.content)
            await chapter_repo.update_chapter(session, match)
            chapter_diff = build_chapter_diff_preview(
                before_match,
                chapter_preview_from_object(match),
            )
            after = images_by_id(await chapter_repo.list_by_project(session, self.project_id))
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

            await safe_maybe_enqueue_auto_index(session, project_id=self.project_id)
            schedule_emit_index_status(session, self.project_id)
            await background_service.commit_and_notify(session)
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": revision_id,
                    "word_count": match.word_count,
                    "chapter": serialize_chapter(match),
                    "chapter_diff": chapter_diff,
                    "affected_chapters": affected,
                    "message": "章节已编辑",
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
