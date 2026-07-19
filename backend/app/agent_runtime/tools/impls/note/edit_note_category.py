# -*- coding: utf-8 -*-
"""
重命名笔记分类。
"""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    note_category_images_by_id,
    record_note_category_diffs,
)
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.note.refs import (
    CategoryRef,
    resolve_category_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import note_category_repo


class EditNoteCategoryInput(BaseModel):
    category_ref: CategoryRef = Field(description="目标分类")
    new_title: str = Field(description="分类的新标题")


@ToolRegistry.register
class EditNoteCategoryTool(AgentTool):
    name: str = "edit_note_category"
    description: str = "重命名指定笔记分类"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditNoteCategoryInput

    async def build_interrupt_preview(self, args: dict[str, Any]) -> dict | None:
        session = self.get_runtime_db_session()
        category_ref = args.get("category_ref")
        new_title = args.get("new_title")
        if session is None or not isinstance(category_ref, dict) or not isinstance(new_title, str):
            return None

        ref = CategoryRef.model_validate(category_ref)
        if ref.id is not None:
            category = await note_category_repo.get_by_id(session, ref.id)
            if category is None or category.project_id != self.project_id:
                return None
            categories = await note_category_repo.list_by_project(session, self.project_id)
        else:
            categories = await note_category_repo.list_by_project(session, self.project_id)
            try:
                category = resolve_category_from_list(categories, ref)
            except ToolExecutionError:
                return None

        if any(
            item.title == new_title
            and item.parent_id == category.parent_id
            and item.id != category.id
            for item in categories
        ):
            return None
        return {
            "type": "preview",
            "success": True,
            "reason": "approval_preview",
            "metadata": {
                "category": {
                    "id": category.id,
                    "title": new_title,
                    "previous_title": category.title,
                    "parent_id": category.parent_id,
                }
            },
        }

    async def _execute(self, category_ref: dict, new_title: str) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行分类重命名")
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

            before = note_category_images_by_id(
                await note_category_repo.list_by_project(session, self.project_id)
            )
            if any(
                item.title == new_title
                and item.parent_id == category.parent_id
                and item.id != category.id
                for item in before.values()
            ):
                raise ToolExecutionError(f"同级分类已存在同名标题: {new_title}")
            previous_title = category.title
            category.title = new_title
            category.updated_at = datetime.now(UTC)
            category = await note_category_repo.update_category(session, category)
            after = note_category_images_by_id(
                await note_category_repo.list_by_project(session, self.project_id)
            )
            await record_note_category_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before,
                after=after,
            )

            from app.background.jobs import service as background_service

            await background_service.commit_and_notify(session)
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "category": {
                            "id": category.id,
                            "title": category.title,
                            "previous_title": previous_title,
                            "parent_id": category.parent_id,
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
