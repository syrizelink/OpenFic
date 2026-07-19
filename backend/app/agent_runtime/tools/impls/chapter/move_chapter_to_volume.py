import json

from pydantic import BaseModel, Field

from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    images_by_id,
    record_agent_activity_for_change,
    record_chapter_diffs,
)
from app.agent_runtime.tools.base import AgentTool
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
from app.storage.services.version_control_service import refresh_project_stats


class MoveChapterToVolumeInput(BaseModel):
    volume_ref: VolumeRef = Field(description="源章节所在的卷")
    chapter_ref: ChapterRef = Field(description="要移动的目标章节")
    target_volume_ref: VolumeRef = Field(description="目标卷；章节会被追加到该卷末尾")


@ToolRegistry.register
class MoveChapterToVolumeTool(AgentTool):
    name: str = "move_chapter_to_volume"
    description: str = "将指定卷内章节移动到目标卷末尾"
    access_level: str = "write"
    args_schema: type[BaseModel] = MoveChapterToVolumeInput

    async def _execute(
        self,
        volume_ref: dict,
        chapter_ref: dict,
        target_volume_ref: dict,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行章节跨卷移动")
        session = await create_session()
        try:
            volumes = await volume_repo.list_by_project(session, self.project_id)
            source_volume = resolve_volume_from_list(
                volumes, VolumeRef.model_validate(volume_ref)
            )
            target_volume = resolve_volume_from_list(
                volumes, VolumeRef.model_validate(target_volume_ref)
            )
            source_chapters = await chapter_repo.list_by_volume(session, source_volume.id)
            chapter = resolve_chapter_from_list(
                source_chapters, ChapterRef.model_validate(chapter_ref)
            )
            before = images_by_id(
                await chapter_repo.list_by_project(session, self.project_id)
            )
            moved = await chapter_service.move_chapter_to_volume(
                session,
                chapter.id,
                target_volume.id,
                record_activity=False,
            )
            after = images_by_id(
                await chapter_repo.list_by_project(session, self.project_id)
            )
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
            await session.commit()
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "chapter_diff": {
                            "operation": "move",
                            "chapter_id": moved.id,
                            "chapter_title": moved.title,
                            "order": moved.order,
                            "volume_id": moved.volume_id,
                        }
                    },
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
