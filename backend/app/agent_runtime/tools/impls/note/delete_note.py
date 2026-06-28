# -*- coding: utf-8 -*-
"""
删除笔记。
"""

import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    note_images_by_id,
    record_note_diffs,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.note.refs import (
    NoteRef,
    resolve_note_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import note_category_repo, note_repo


class DeleteNoteInput(BaseModel):
    note_ref: NoteRef = Field(description="要删除的笔记引用")


@ToolRegistry.register
class DeleteNoteTool(AgentTool):
    name: str = "delete_note"
    description: str = "删除指定笔记"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteNoteInput

    async def _execute(self, note_ref: dict) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行笔记删除")
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
            if note.is_locked:
                raise ToolExecutionError("该笔记已锁定，无法删除")
            if note.is_hidden:
                raise ToolExecutionError("该笔记已隐藏")

            before = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            old_title = note.title
            await note_repo.delete(session, note)
            after = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            affected = await record_note_diffs(
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
                    "title": old_title,
                    "affected_notes": affected,
                    "message": "笔记已删除",
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
