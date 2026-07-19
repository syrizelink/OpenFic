# -*- coding: utf-8 -*-
"""
删除笔记分类及其下的所有内容。
"""

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    note_category_images_by_id,
    note_images_by_id,
    record_note_category_diffs,
    record_note_diffs,
)
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.note.refs import CategoryRef, resolve_category_from_list
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.models.note import NoteCategory
from app.storage.repos import note_category_repo, note_repo
from app.storage.services import note_service


class DeleteNoteCategoryInput(BaseModel):
    category_ref: CategoryRef = Field(description="目标分类")


def _collect_descendant_category_ids(
    category_id: str,
    categories: list[NoteCategory],
) -> set[str]:
    affected_ids = {category_id}
    while True:
        child_ids = {
            category.id
            for category in categories
            if category.parent_id in affected_ids and category.id not in affected_ids
        }
        if not child_ids:
            return affected_ids
        affected_ids.update(child_ids)


@ToolRegistry.register
class DeleteNoteCategoryTool(AgentTool):
    name: str = "delete_note_category"
    description: str = "删除指定笔记分类及其下的子分类和笔记"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteNoteCategoryInput

    async def build_interrupt_preview(self, args: dict[str, Any]) -> dict | None:
        session = self.get_runtime_db_session()
        category_ref = args.get("category_ref")
        if session is None or not isinstance(category_ref, dict):
            return None

        ref = CategoryRef.model_validate(category_ref)
        categories = await note_category_repo.list_by_project(session, self.project_id)
        try:
            category = (
                await note_category_repo.get_by_id(session, ref.id)
                if ref.id is not None
                else resolve_category_from_list(categories, ref)
            )
        except ToolExecutionError:
            return None
        if category is None or category.project_id != self.project_id:
            return None

        affected_category_ids = _collect_descendant_category_ids(category.id, categories)
        notes = await note_repo.list_by_project(
            session, self.project_id, include_hidden=True
        )
        return {
            "type": "preview",
            "success": True,
            "reason": "approval_preview",
            "metadata": {
                "category": {
                    "id": category.id,
                    "title": category.title,
                },
                "affected_category_count": len(affected_category_ids),
                "affected_note_count": sum(
                    note.category_id in affected_category_ids for note in notes
                ),
            },
        }

    async def _execute(self, category_ref: dict) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行分类删除")
        session = await create_session()
        try:
            ref = CategoryRef.model_validate(category_ref)
            if ref.id is not None:
                category = await note_category_repo.get_by_id(session, ref.id)
                if category is None:
                    raise ToolExecutionError(f"分类不存在: {ref.id}")
            else:
                categories = await note_category_repo.list_by_project(
                    session, self.project_id
                )
                category = resolve_category_from_list(categories, ref)
            if category.project_id != self.project_id:
                raise ToolExecutionError("分类不属于当前项目")

            before_categories = note_category_images_by_id(
                await note_category_repo.list_by_project(session, self.project_id)
            )
            before_notes = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            category_id = category.id
            category_title = category.title
            await note_service.delete_category(session, category_id)
            after_categories = note_category_images_by_id(
                await note_category_repo.list_by_project(session, self.project_id)
            )
            after_notes = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            await record_note_category_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before_categories,
                after=after_categories,
            )
            await record_note_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before_notes,
                after=after_notes,
            )

            from app.background.jobs import service as background_service

            await background_service.commit_and_notify(session)
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "category": {
                            "id": category_id,
                            "title": category_title,
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
