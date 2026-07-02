# -*- coding: utf-8 -*-
"""
创建新笔记。
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
    generate_unique_title,
    resolve_category_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.models.note import Note
from app.storage.repos import note_category_repo, note_repo


class WriteNoteInput(BaseModel):
    title: str = Field(description="笔记标题")
    content: str = Field(description="笔记内容")
    category_ref: dict | None = Field(default=None, description="可选的目标分类引用")


@ToolRegistry.register
class WriteNoteTool(AgentTool):
    name: str = "write_note"
    description: str = "在指定分类（可省略）下创建新笔记"
    access_level: str = "write"
    args_schema: type[BaseModel] = WriteNoteInput

    async def _execute(
        self,
        title: str,
        content: str,
        category_ref: dict | None = None,
    ) -> str:
        revision_id = current_revision_id_from_state(self._state)
        if revision_id is None:
            raise ToolExecutionError("缺少当前 revision，无法执行笔记写入")
        session = await create_session()
        try:
            category_id: str | None = None
            if category_ref is not None:
                ref = CategoryRef.model_validate(category_ref)
                if ref.id is not None:
                    cat = await note_category_repo.get_by_id(session, ref.id)
                    if cat is None:
                        raise ToolExecutionError(f"分类不存在: {ref.id}")
                else:
                    cats = await note_category_repo.list_by_project(
                        session, self.project_id
                    )
                    cat = resolve_category_from_list(cats, ref)
                if cat.project_id != self.project_id:
                    raise ToolExecutionError("目标分类不属于当前项目")
                category_id = cat.id

            notes = await note_repo.list_by_project(
                session, self.project_id, include_hidden=False
            )
            sibling_titles = {
                n.title for n in notes if n.category_id == category_id
            }
            unique_title = generate_unique_title(title, sibling_titles)

            before = note_images_by_id(
                await note_repo.list_by_project(
                    session, self.project_id, include_hidden=True
                )
            )
            note = Note(
                project_id=self.project_id,
                category_id=category_id,
                title=unique_title,
                content=content,
                is_locked=False,
                is_hidden=False,
            )
            note = await note_repo.create(session, note)
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

            content_lines = content.splitlines()
            diff_lines = [
                {
                    "type": "added",
                    "before_line_number": None,
                    "after_line_number": i + 1,
                    "text": line,
                }
                for i, line in enumerate(content_lines)
            ]
            note_diff = {
                "operation": "create",
                "sections": [{"type": "content", "lines": diff_lines}],
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
                        "category_id": note.category_id,
                    },
                    "note_diff": note_diff,
                    "affected_notes": affected,
                    "message": f"笔记已创建: {note.title}"
                    if unique_title != title
                    else "笔记已创建",
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
