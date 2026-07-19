# -*- coding: utf-8 -*-
"""
读取单条笔记内容。
"""

import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.note.refs import (
    NoteRef,
    resolve_note_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import note_category_repo, note_repo


class ReadNoteInput(BaseModel):
    note_ref: NoteRef = Field(description="目标笔记")


@ToolRegistry.register
class ReadNoteTool(AgentTool):
    name: str = "read_note"
    description: str = "读取指定笔记的完整内容"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadNoteInput

    async def _execute(self, note_ref: dict) -> str:
        session = await create_session()
        try:
            ref = NoteRef.model_validate(note_ref)
            if ref.id is not None:
                note = await note_repo.get_by_id(session, ref.id)
                if note is None:
                    raise ToolExecutionError(f"笔记不存在: {ref.id}")
            else:
                notes = await note_repo.list_by_project(
                    session, self.project_id, include_hidden=False
                )
                cats = await note_category_repo.list_by_project(
                    session, self.project_id
                )
                note = resolve_note_from_list(notes, ref, categories=cats)

            if note.project_id != self.project_id:
                raise ToolExecutionError("笔记不属于当前项目")

            if note.is_hidden:
                raise ToolExecutionError("该笔记已隐藏")

            return json.dumps(
                {
                    "id": note.id,
                    "title": note.title,
                    "content": note.content,
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()
