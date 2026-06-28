# -*- coding: utf-8 -*-
"""
移动笔记到目标分类。
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
    CategoryRef,
    NoteRef,
    resolve_category_from_list,
    resolve_note_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import note_category_repo, note_repo
from app.storage.services import note_service


class MoveNoteInput(BaseModel):
    note_ref: NoteRef = Field(description="要移动的笔记引用")
    target_category_ref: dict | None = Field(
        default=None, description="目标分类引用；None 表示移到根层级"
    )


@ToolRegistry.register
class MoveNoteTool(AgentTool):
    name: str = "move_note"
    description: str = "将笔记移动到指定分类下"
    access_level: str = "write"
    args_schema: type[BaseModel] = MoveNoteInput

    async def _execute(
        self,
        note_ref: dict,
        target_category_ref: dict | None = None,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行笔记移动")
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
                raise ToolExecutionError("该笔记已锁定，无法移动")
            if note.is_hidden:
                raise ToolExecutionError("该笔记已隐藏")

            target_category_id: str | None = None
            target_category_title: str | None = None
            if target_category_ref is not None:
                tref = CategoryRef.model_validate(target_category_ref)
                if tref.id is not None:
                    target = await note_category_repo.get_by_id(session, tref.id)
                    if target is None:
                        raise ToolExecutionError(f"分类不存在: {tref.id}")
                else:
                    cats = await note_category_repo.list_by_project(
                        session, self.project_id
                    )
                    target = resolve_category_from_list(cats, tref)
                if target.project_id != self.project_id:
                    raise ToolExecutionError("目标分类不属于当前项目")
                target_category_id = target.id
                target_category_title = target.title

            before = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            moved = await note_service.move_item(
                session, "note", note.id, target_category_id
            )
            moved_category_id = getattr(moved, "category_id", None)
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
                    "note": {
                        "id": moved.id,
                        "title": moved.title,
                        "category_id": moved_category_id,
                    },
                    "target_category": {
                        "id": target_category_id,
                        "title": target_category_title,
                    } if target_category_id else None,
                    "affected_notes": affected,
                    "message": "笔记已移动",
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
