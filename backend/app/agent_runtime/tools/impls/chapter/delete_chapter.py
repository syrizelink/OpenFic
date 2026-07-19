import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    images_by_id,
    record_agent_activity_for_change,
    record_chapter_diffs,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.chapter.refs import (
    ChapterRef,
    VolumeRef,
    resolve_chapter_from_list,
    resolve_volume_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo
from app.storage.services import chapter_service


class DeleteChapterInput(BaseModel):
    volume_ref: VolumeRef = Field(description="目标章节所在的卷")
    chapter_ref: ChapterRef = Field(description="要删除的目标章节")


@ToolRegistry.register
class DeleteChapterTool(AgentTool):
    name: str = "delete_chapter"
    description: str = "删除指定章节，删除后，卷内章节序号会自动调整"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteChapterInput

    async def _execute(self, volume_ref: dict, chapter_ref: dict) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行章节删除")
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
            await chapter_service.delete_chapter(
                session,
                match.id,
                activity_source="agent",
                revision_id=revision_id,
                task_id=str(self._state.get("task_id") or ""),
                agent_session_id=self.session_id,
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
            await session.commit()
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "chapter_diff": {
                            "operation": "delete",
                            "chapter_id": match.id,
                            "chapter_title": match.title,
                            "order": match.order,
                        }
                    },
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
