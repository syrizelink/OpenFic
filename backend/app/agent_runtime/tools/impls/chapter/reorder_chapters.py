import json
from dataclasses import replace

from pydantic import BaseModel, Field

from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    images_by_id,
    record_agent_activity_for_change,
    record_chapter_diffs,
)
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls._locks import keyed_locks
from app.agent_runtime.tools.impls.chapter.refs import (
    ChapterRef,
    VolumeRef,
    resolve_volume_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo
from app.storage.services import chapter_service
from app.storage.services.version_control_service import refresh_project_stats


class ReorderChaptersInput(BaseModel):
    volume_ref: VolumeRef = Field(description="目标卷")
    ordered_chapter_refs: list[ChapterRef] = Field(
        description="按新顺序排列的章节引用列表，必须包含该卷内全部章节，不允许遗漏或多余",
    )


@ToolRegistry.register
class ReorderChaptersTool(AgentTool):
    name: str = "reorder_chapters"
    description: str = "重排指定卷内的章节顺序，传入按新顺序排列的章节引用列表（须覆盖卷内全部章节）"
    access_level: str = "write"
    args_schema: type[BaseModel] = ReorderChaptersInput

    async def _execute(
        self,
        volume_ref: dict,
        ordered_chapter_refs: list[dict],
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行章节重排")
        session = await create_session()
        try:
            volumes = await volume_repo.list_by_project(session, self.project_id)
            volume = resolve_volume_from_list(
                volumes, VolumeRef.model_validate(volume_ref)
            )
            volume_id = volume.id

            volume_chapters = await chapter_repo.list_by_volume(session, volume_id)
            ref_models = [ChapterRef.model_validate(ref) for ref in ordered_chapter_refs]

            # 将每个传入的章节引用解析为卷内的具体章节
            resolved: list = []
            used_ids: set[str] = set()
            for ref_model in ref_models:
                matched = await chapter_repo.get_by_volume_ref(
                    session,
                    volume_id,
                    ref_type=ref_model.type,
                    ref_value=ref_model.value,
                )
                if matched is None:
                    raise ToolExecutionError(
                        f"未在卷「{volume.title}」中找到章节（{ref_model.type}={ref_model.value}）"
                    )
                if matched.id in used_ids:
                    raise ToolExecutionError(
                        f"章节引用重复：{matched.title}（{ref_model.type}={ref_model.value}）"
                    )
                used_ids.add(matched.id)
                resolved.append(matched)

            existing_ids = {chapter.id for chapter in volume_chapters}
            if used_ids != existing_ids:
                missing = [
                    chapter.title
                    for chapter in volume_chapters
                    if chapter.id not in used_ids
                ]
                extra = [
                    chapter.title
                    for chapter in resolved
                    if chapter.id not in existing_ids
                ]
                raise ToolExecutionError(
                    "章节引用必须与卷内现有章节一一对应："
                    f"缺少 {missing or '无'}；多余 {extra or '无'}"
                )

            before = images_by_id(volume_chapters)
            ordered_ids = [chapter.id for chapter in resolved]
            # rollback 会使 ORM 对象 expire；title 等展示字段必须在 rollback 前取出纯值。
            volume_title = volume.title.strip()
            await session.rollback()

            async with keyed_locks([("chapters", self.project_id)]):
                updated = await chapter_service.reorder_chapters(
                    session, volume_id, ordered_ids
                )
                # reorder 不改正文：以 before 快照为底，仅替换 order 字段，
                # 避免 metadata-only 对象访问 .content 触发同步 lazy load（MissingGreenlet）。
                after = {
                    chapter.id: replace(before[chapter.id], order=chapter.order)
                    for chapter in updated
                }
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
                            "volume": volume_title,
                            "new_order": [
                                {
                                    "order": chapter.order,
                                    "title": chapter.title,
                                }
                                for chapter in sorted(
                                    updated, key=lambda chapter: chapter.order or 0
                                )
                            ],
                        },
                    },
                    ensure_ascii=False,
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
