# -*- coding: utf-8 -*-
"""
创建笔记分类。
"""

import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    note_category_images_by_id,
    record_note_category_diffs,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.note.refs import (
    CategoryRef,
    generate_unique_title,
    resolve_category_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.models.note import NoteCategory
from app.storage.repos import note_category_repo


class CreateNoteCategoryInput(BaseModel):
    title: str = Field(description="分类标题")
    parent_ref: dict | None = Field(
        default=None, description="可选的父分类引用；省略则创建在根层级"
    )


@ToolRegistry.register
class CreateNoteCategoryTool(AgentTool):
    name: str = "create_note_category"
    description: str = "在指定父分类下创建新分类"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateNoteCategoryInput

    async def _execute(
        self,
        title: str,
        parent_ref: dict | None = None,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行分类创建")
        session = await create_session()
        try:
            parent_id: str | None = None
            if parent_ref is not None:
                ref = CategoryRef.model_validate(parent_ref)
                if ref.id is not None:
                    parent = await note_category_repo.get_by_id(session, ref.id)
                    if parent is None:
                        raise ToolExecutionError(f"分类不存在: {ref.id}")
                else:
                    cats = await note_category_repo.list_by_project(
                        session, self.project_id
                    )
                    parent = resolve_category_from_list(cats, ref)
                if parent.project_id != self.project_id:
                    raise ToolExecutionError("父分类不属于当前项目")
                parent_id = parent.id

            before = note_category_images_by_id(
                await note_category_repo.list_by_project(session, self.project_id)
            )
            sibling_titles = {
                c.title for c in before.values() if c.parent_id == parent_id
            }
            unique_title = generate_unique_title(title, sibling_titles)

            category = NoteCategory(
                project_id=self.project_id,
                parent_id=parent_id,
                title=unique_title,
            )
            category = await note_category_repo.create(session, category)
            after = note_category_images_by_id(
                await note_category_repo.list_by_project(session, self.project_id)
            )
            affected = await record_note_category_diffs(
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
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": revision_id,
                    "category": {
                        "id": category.id,
                        "title": category.title,
                        "parent_id": category.parent_id,
                    },
                    "affected_note_categories": affected,
                    "message": f"分类已创建: {category.title}"
                    if unique_title != title
                    else "分类已创建",
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
