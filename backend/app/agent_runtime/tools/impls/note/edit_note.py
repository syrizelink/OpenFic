# -*- coding: utf-8 -*-
"""
编辑笔记内容（查找替换）。
"""

import json
from difflib import SequenceMatcher
from typing import Any

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


def _build_diff_lines(before: str, after: str) -> list[dict[str, Any]]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    lines: list[dict[str, Any]] = []
    before_line_number = 1
    after_line_number = 1

    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            before_line_number += before_end - before_start
            after_line_number += after_end - after_start
            continue

        if tag in {"delete", "replace"}:
            for line in before_lines[before_start:before_end]:
                lines.append({
                    "type": "removed",
                    "before_line_number": before_line_number,
                    "after_line_number": None,
                    "text": line,
                })
                before_line_number += 1

        if tag in {"insert", "replace"}:
            for line in after_lines[after_start:after_end]:
                lines.append({
                    "type": "added",
                    "before_line_number": None,
                    "after_line_number": after_line_number,
                    "text": line,
                })
                after_line_number += 1

    return lines


class EditNoteInput(BaseModel):
    note_ref: NoteRef = Field(description="要编辑的笔记引用")
    old_content: str = Field(description="要查找并替换的原始文本")
    new_content: str = Field(description="用于替换的新文本")


@ToolRegistry.register
class EditNoteTool(AgentTool):
    name: str = "edit_note"
    description: str = "编辑笔记内容，使用查找替换模式"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditNoteInput

    async def _execute(
        self,
        note_ref: dict,
        old_content: str,
        new_content: str,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行笔记编辑")
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
                raise ToolExecutionError("该笔记已锁定，无法修改")
            if note.is_hidden:
                raise ToolExecutionError("该笔记已隐藏")

            if old_content not in note.content:
                raise ToolExecutionError("未在笔记内容中找到要替换的文本")

            before = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            before_content = note.content
            note.content = note.content.replace(old_content, new_content)
            await note_repo.update_note(session, note)
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

            diff_lines = _build_diff_lines(before_content, note.content)
            note_diff = {
                "operation": "update",
                "sections": [{"label": "内容", "lines": diff_lines}],
                "note_id": note.id,
                "note_title": note.title,
            }

            from app.background.jobs import service as background_service

            await background_service.commit_and_notify(session)
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": revision_id,
                    "note": {
                        "id": note.id,
                        "title": note.title,
                    },
                    "note_diff": note_diff,
                    "affected_notes": affected,
                    "message": "笔记已编辑",
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
