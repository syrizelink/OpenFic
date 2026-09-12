# -*- coding: utf-8 -*-
"""
Menyunting isi catatan (cari dan ganti).
"""

import json
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.tools.base import AgentTool
from app.core.editor_content_limits import EditorContentLimitError, validate_editor_content
from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    note_images_by_id,
    record_note_diffs,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.note.refs import (
    NoteRef,
    build_category_path,
    resolve_note_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.agent_runtime.tools.text_match import fuzzy_replace
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
    note_ref: NoteRef = Field(description="Catatan sasaran")
    old_content: str = Field(description="Teks asli yang akan dicari dan diganti")
    new_content: str = Field(
        description="Teks baru sebagai pengganti old_content"
    )

    @field_validator("old_content", mode="after")
    @classmethod
    def reject_empty_old_content(cls, v: str) -> str:
        if v == "":
            raise ValueError("old_content tidak boleh berupa string kosong")
        return v


@ToolRegistry.register
class EditNoteTool(AgentTool):
    name: str = "edit_note"
    description: str = "Menyunting isi catatan yang ditentukan"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditNoteInput

    async def build_interrupt_preview(self, args: dict[str, Any]) -> dict | None:
        session = self.get_runtime_db_session()
        note_ref = args.get("note_ref")
        old_content = args.get("old_content")
        new_content = args.get("new_content")
        if (
            session is None
            or not isinstance(note_ref, dict)
            or not isinstance(old_content, str)
            or not isinstance(new_content, str)
        ):
            return None

        categories = []
        ref = NoteRef.model_validate(note_ref)
        if ref.id is not None:
            note = await note_repo.get_by_id(session, ref.id)
            if note is None:
                return None
        else:
            notes = await note_repo.list_by_project(session, self.project_id, include_hidden=False)
            categories = await note_category_repo.list_by_project(session, self.project_id)
            try:
                note = resolve_note_from_list(notes, ref, categories=categories)
            except ToolExecutionError:
                return None

        if note.category_id is not None and not categories:
            categories = await note_category_repo.list_by_project(session, self.project_id)

        if (
            note.project_id != self.project_id
            or note.is_locked
            or note.is_hidden
        ):
            return None

        preview_result = fuzzy_replace(
            note.content, old_content, new_content, replace_all=True
        )
        if preview_result is None:
            return None
        preview_content = preview_result.new_content
        try:
            validate_editor_content(preview_content)
        except EditorContentLimitError:
            return None
        note_diff = {
            "operation": "update",
            "note_id": note.id,
            "note_title": note.title,
            "sections": [
                {
                    "type": "content",
                    "lines": _build_diff_lines(note.content, preview_content),
                }
            ],
        }
        category_path = build_category_path(categories, note.category_id)
        if category_path:
            note_diff["path"] = category_path
        return {
            "type": "preview",
            "success": True,
            "reason": "approval_preview",
            "message": "Perubahan catatan menunggu persetujuan",
            "metadata": {
                "note_diff": note_diff,
            },
        }

    async def _execute(
        self,
        note_ref: dict,
        old_content: str,
        new_content: str,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError(
                "revision saat ini tidak ada, penyuntingan catatan tidak dapat "
                "dijalankan"
            )
        session = await create_session()
        try:
            categories = []
            ref = NoteRef.model_validate(note_ref)
            if ref.id is not None:
                note = await note_repo.get_by_id(session, ref.id)
                if note is None:
                    raise ToolExecutionError(f"Catatan tidak ditemukan: {ref.id}")
            else:
                notes = await note_repo.list_by_project(
                    session, self.project_id, include_hidden=False
                )
                categories = await note_category_repo.list_by_project(
                    session, self.project_id
                )
                note = resolve_note_from_list(notes, ref, categories=categories)

            if note.category_id is not None and not categories:
                categories = await note_category_repo.list_by_project(
                    session, self.project_id
                )

            if note.project_id != self.project_id:
                raise ToolExecutionError("Catatan tidak termasuk dalam proyek saat ini")
            if note.is_locked:
                raise ToolExecutionError(
                    "Catatan ini terkunci sehingga tidak dapat diubah"
                )
            if note.is_hidden:
                raise ToolExecutionError("Catatan ini sudah disembunyikan")

            before = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            before_content = note.content
            replace_result = fuzzy_replace(
                note.content, old_content, new_content, replace_all=True
            )
            if replace_result is None:
                raise ToolExecutionError(
                    "Teks yang akan diganti tidak ditemukan di dalam isi catatan"
                )
            note.content = replace_result.new_content
            try:
                validate_editor_content(note.content)
            except EditorContentLimitError as exc:
                raise ToolExecutionError(str(exc)) from exc
            note.updated_at = datetime.now(UTC)
            await note_repo.update_note(session, note)
            after = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            await record_note_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before,
                after=after,
            )

            diff_lines = _build_diff_lines(before_content, note.content)
            note_diff = {
                "operation": "update",
                "sections": [{"type": "content", "lines": diff_lines}],
                "note_id": note.id,
                "note_title": note.title,
            }
            category_path = build_category_path(categories, note.category_id)
            if category_path:
                note_diff["path"] = category_path

            from app.background.jobs import service as background_service

            await background_service.commit_and_notify(session)
            return json.dumps(
                {
                    "success": True,
                    "metadata": {"note_diff": note_diff},
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
