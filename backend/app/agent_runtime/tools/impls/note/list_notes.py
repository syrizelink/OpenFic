# -*- coding: utf-8 -*-
"""
列出某分类下的直接子项（笔记 + 子分类）。
"""

import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import note_category_repo, note_repo


class ListNotesInput(BaseModel):
    path: str = Field(
        default="/",
        description="分类路径，如 /、/设定、/设定/角色。'/' 表示根层级",
    )


@ToolRegistry.register
class ListNotesTool(AgentTool):
    name: str = "list_notes"
    description: str = (
        "列出指定分类路径下的直接子项（笔记和子分类，不递归）。"
        "'/' 表示根层级，返回根下的笔记和分类"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListNotesInput

    async def _execute(self, path: str = "/") -> str:
        session = await create_session()
        try:
            categories = await note_category_repo.list_by_project(
                session, self.project_id
            )
            notes = await note_repo.list_by_project(
                session, self.project_id, include_hidden=False
            )

            target_category_id: str | None = None
            if path == "/":
                target_category_id = None
            else:
                segments = [s for s in path.strip("/").split("/") if s]
                current_id: str | None = None
                for segment in segments:
                    children = [
                        c
                        for c in categories
                        if c.parent_id == current_id and c.title == segment
                    ]
                    if not children:
                        return json.dumps(
                            {"error": f"未找到路径: {path}"}, ensure_ascii=False
                        )
                    current_id = children[0].id
                target_category_id = current_id

            sub_categories = [
                c for c in categories if c.parent_id == target_category_id
            ]
            sub_notes = [n for n in notes if n.category_id == target_category_id]

            items: list[dict] = []
            for cat in sorted(sub_categories, key=lambda c: c.title):
                items.append({"type": "category", "id": cat.id, "title": cat.title})
            for note in sorted(sub_notes, key=lambda n: n.title):
                items.append({"type": "note", "id": note.id, "title": note.title})

            return json.dumps({"path": path, "items": items}, ensure_ascii=False)
        finally:
            await session.close()
