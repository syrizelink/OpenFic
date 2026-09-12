# -*- coding: utf-8 -*-
"""
Menampilkan anak langsung di bawah suatu kategori (catatan + sub-kategori).
"""

import json
from textwrap import dedent

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import note_category_repo, note_repo


class ListNotesInput(BaseModel):
    path: str = Field(
        default="/",
        description=dedent("""\
        Jalur kategori, misalnya `/`, `/latar`, `/latar/tokoh`;
        `/` berarti tingkat akar, mengembalikan semua catatan dan kategori di
        bawah akar
    """)
    )


@ToolRegistry.register
class ListNotesTool(AgentTool):
    name: str = "list_notes"
    description: str = (
        "Menampilkan anak langsung di bawah jalur kategori yang ditentukan "
        "(mencakup catatan dan kategori, tidak rekursif)"
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
                            {"error": f"Jalur tidak ditemukan: {path}"},
                            ensure_ascii=False,
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
