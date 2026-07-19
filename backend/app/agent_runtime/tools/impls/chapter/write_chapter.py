import json
import re
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    images_by_id,
    record_agent_activity_for_change,
    record_chapter_diffs,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.chapter.diff_preview import (
    build_chapter_diff_preview,
    build_write_chapter_tool_result_preview,
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
from app.storage.models.chapter import Chapter
from app.storage.repos import chapter_repo, volume_repo
from app.storage.services.volume_service import refresh_volume_chapter_count
from app.storage.services.version_control_service import refresh_project_stats


def count_words(text: str) -> int:
    if not text:
        return 0
    chinese_chars = re.findall(r"[一-鿿]", text)
    text_without_chinese = re.sub(r"[一-鿿]", " ", text)
    english_words = [w for w in text_without_chinese.split() if w.strip()]
    return len(chinese_chars) + len(english_words)


class WriteChapterInput(BaseModel):
    volume_ref: VolumeRef = Field(description="目标卷")
    title: str = Field(description="标题")
    content: str = Field(description="正文内容")
    chapter_ref: ChapterRef | None = Field(
        default=None,
        description="插入位置，可选；传入时章节会被插入到指定章节之前，否则会被追加到卷末",
    )


@ToolRegistry.register
class WriteChapterTool(AgentTool):
    name: str = "write_chapter"
    description: str = "创建一个新章节"
    access_level: str = "write"
    args_schema: type[BaseModel] = WriteChapterInput

    async def build_interrupt_preview(self, args: dict[str, Any]) -> dict | None:
        session = self.get_runtime_db_session()
        if session is None:
            return None
        title = args.get("title")
        content = args.get("content")
        if not isinstance(title, str) or not isinstance(content, str):
            return None
        volume_ref = args.get("volume_ref")
        if isinstance(volume_ref, VolumeRef):
            volume_ref = volume_ref.model_dump()
        if not isinstance(volume_ref, dict):
            return None
        chapter_ref = args.get("chapter_ref")
        return await build_write_chapter_tool_result_preview(
            session,
            self.project_id,
            volume_ref=volume_ref,
            title=title,
            content=content,
            chapter_ref=chapter_ref if isinstance(chapter_ref, dict) else None,
        )

    async def _execute(
        self,
        volume_ref: dict,
        title: str,
        content: str,
        chapter_ref: dict | None = None,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行章节写入")
        session = await create_session()
        try:
            volume = resolve_volume_from_list(
                await volume_repo.list_by_project(session, self.project_id),
                VolumeRef.model_validate(volume_ref),
            )
            before = images_by_id(await chapter_repo.list_by_project(session, self.project_id))
            max_order = await chapter_repo.get_max_order(session, volume.id)
            if chapter_ref is not None:
                ref = ChapterRef.model_validate(chapter_ref)
                chapters = await chapter_repo.list_by_volume(session, volume.id)
                match = resolve_chapter_from_list(chapters, ref)
                insert_order = match.order
                await chapter_repo.shift_orders(
                    session, volume.id, insert_order, max_order, 1
                )
                order = insert_order
            else:
                order = max_order + 1
            chapter = Chapter(
                project_id=self.project_id,
                volume_id=volume.id,
                title=title,
                content=content,
                word_count=count_words(content),
                order=order,
            )
            chapter = await chapter_repo.create(session, chapter)
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
            await refresh_volume_chapter_count(session, volume.id)
            await refresh_project_stats(session, self.project_id)
            from app.background.jobs import service as background_service
            from app.retrieval.chapter_index import safe_maybe_enqueue_auto_index
            from app.retrieval.index_status import schedule_emit_index_status

            await safe_maybe_enqueue_auto_index(session, project_id=self.project_id)
            schedule_emit_index_status(session, self.project_id)
            await background_service.commit_and_notify(session)
            chapter_diff = build_chapter_diff_preview(
                None,
                chapter_preview_from_object(chapter),
            )
            return json.dumps(
                {
                    "success": True,
                    "word_count": chapter.word_count,
                    "metadata": {"chapter_diff": chapter_diff},
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
