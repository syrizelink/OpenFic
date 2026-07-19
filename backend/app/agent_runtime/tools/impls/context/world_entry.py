import json
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.revisions import (
    current_revision_id_from_state,
    record_world_entry_diffs,
    world_entry_images_by_id,
)
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.models.world_info_entry import WorldInfoEntry
from app.storage.repos import world_info_entry_repo, world_info_repo
from app.storage.services import world_info_entry_service


class ListWorldEntriesInput(BaseModel):
    pass


class ReadWorldEntryInput(BaseModel):
    title: str = Field(description="条目标题")


class CreateWorldEntryInput(BaseModel):
    title: str = Field(description="条目标题")
    content: str = Field(description="条目内容")


class EditWorldEntryInput(BaseModel):
    title: str = Field(description="条目标题")
    new_title: str | None = Field(default=None, description="新条目标题，可选")
    old_content: str | None = Field(default=None, description="要查找并替换的原始文本")
    new_content: str | None = Field(default=None, description="用于替换 old_content 的新文本")
    replace_all: bool = Field(default=False, description="是否替换命中的全部 old_content，false 时只替换首个匹配项")

    @field_validator("new_content", mode="after")
    @classmethod
    def check_edit_fields(cls, v, info):
        data = info.data
        has_title = data.get("new_title") is not None
        has_content = data.get("old_content") is not None and v is not None
        if not has_title and not has_content:
            raise ValueError("new_title 和 old_content/new_content 必填其中一类")
        return v


class DeleteWorldEntryInput(BaseModel):
    title: str = Field(description="条目标题")


@dataclass(frozen=True)
class WorldEntryPreview:
    id: str
    title: str
    uid: int
    order: int
    content: str
    token_count: int
    is_enabled: bool


def _preview_from_entry(entry: WorldInfoEntry) -> WorldEntryPreview:
    return WorldEntryPreview(
        id=entry.id,
        title=entry.name,
        uid=entry.uid,
        order=entry.order,
        content=entry.content,
        token_count=getattr(entry, "token_count", 0),
        is_enabled=getattr(entry, "is_enabled", True),
    )


def _format_content_with_line_numbers(content: str) -> str:
    if not content:
        return ""
    return "\n".join(
        f"{line_number}|{line}"
        for line_number, line in enumerate(content.splitlines(), start=1)
    )


def _diff_lines(before: str | None, after: str | None) -> list[dict]:
    lines: list[dict] = []
    if before is not None:
        lines.extend(
            {
                "type": "removed",
                "before_line_number": line_number,
                "after_line_number": None,
                "text": line,
            }
            for line_number, line in enumerate(before.splitlines() or [""], start=1)
        )
    if after is not None:
        lines.extend(
            {
                "type": "added",
                "before_line_number": None,
                "after_line_number": line_number,
                "text": line,
            }
            for line_number, line in enumerate(after.splitlines() or [""], start=1)
        )
    return lines


def _build_world_entry_diff(
    before: WorldEntryPreview | None,
    after: WorldEntryPreview | None,
) -> dict:
    target = after or before
    if target is None:
        raise ToolExecutionError("缺少世界书条目 diff 数据")
    if before is None:
        operation = "create"
        lines = _diff_lines(None, after.content if after else "")
    elif after is None:
        operation = "delete"
        lines = _diff_lines(before.content, None)
    else:
        operation = "edit"
        lines = _diff_lines(before.content, after.content) if before.content != after.content else []
    return {
        "operation": operation,
        "entry_id": target.id,
        "entry_title": target.title,
        "sections": [{"type": "content", "lines": lines}],
    }


async def _get_project_world_info(session, project_id: str):
    world_info = await world_info_repo.get_by_project_id(session, project_id)
    if world_info is None:
        raise ToolExecutionError("当前项目未绑定世界书")
    return world_info


async def _resolve_entry_by_title(session, world_info_id: str, title: str) -> WorldInfoEntry:
    normalized_title = title.strip()
    if not normalized_title:
        raise ToolExecutionError("世界书条目标题不能为空")
    entries = await world_info_entry_repo.list_by_world_info(
        session, world_info_id, offset=0, limit=10000
    )
    matches = [entry for entry in entries if entry.name == normalized_title]
    if not matches:
        raise ToolExecutionError(f"世界书条目不存在: {normalized_title}")
    if len(matches) > 1:
        raise ToolExecutionError(f"世界书条目标题不唯一: {normalized_title}")
    return matches[0]


async def _ensure_title_available(
    session,
    world_info_id: str,
    title: str,
    exclude_entry_id: str | None = None,
) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise ToolExecutionError("世界书条目标题不能为空")
    entries = await world_info_entry_repo.list_by_world_info(
        session, world_info_id, offset=0, limit=10000
    )
    if any(
        entry.name == normalized_title and entry.id != exclude_entry_id for entry in entries
    ):
        raise ToolExecutionError(f"世界书条目标题已存在: {normalized_title}")
    return normalized_title


def _require_revision_id(state: dict) -> str:
    revision_id = current_revision_id_from_state(state)
    if revision_id is None:
        raise ToolExecutionError("缺少当前 revision，无法执行世界书条目修改")
    return revision_id


@ToolRegistry.register
class ListWorldEntriesTool(AgentTool):
    name: str = "list_world_entries"
    description: str = "获取项目世界书中启用的设定条目列表"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListWorldEntriesInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            world_info = await _get_project_world_info(session, self.project_id)
            entries = await world_info_entry_repo.list_enabled_by_world_info(
                session, world_info.id
            )
            return json.dumps(
                {
                    "entries": [
                        {"title": entry.name, "uid": entry.uid, "order": entry.order}
                        for entry in entries
                    ]
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()


@ToolRegistry.register
class ReadWorldEntryTool(AgentTool):
    name: str = "read_world_entry"
    description: str = "读取项目世界书中指定的设定条目内容"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadWorldEntryInput

    async def _execute(self, title: str) -> str:
        session = await create_session()
        try:
            world_info = await _get_project_world_info(session, self.project_id)
            entry = await _resolve_entry_by_title(session, world_info.id, title)
            return json.dumps(
                {
                    "title": entry.name,
                    "uid": entry.uid,
                    "order": entry.order,
                    "content": _format_content_with_line_numbers(entry.content),
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()


@ToolRegistry.register
class CreateWorldEntryTool(AgentTool):
    name: str = "create_world_entry"
    description: str = "在项目世界书中创建设定条目"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateWorldEntryInput

    async def _execute(self, title: str, content: str) -> str:
        revision_id = _require_revision_id(self._state)
        session = await create_session()
        try:
            world_info = await _get_project_world_info(session, self.project_id)
            normalized_title = await _ensure_title_available(session, world_info.id, title)
            entry = await world_info_entry_service.create_entry(
                session,
                world_info.id,
                name=normalized_title,
                content=content,
                is_enabled=True,
            )
            await record_world_entry_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before={},
                after=world_entry_images_by_id([entry], project_id=self.project_id),
            )
            await session.commit()
            entry_preview = _preview_from_entry(entry)
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "world_info_id": world_info.id,
                        "world_entry_diff": _build_world_entry_diff(None, entry_preview),
                    },
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@ToolRegistry.register
class EditWorldEntryTool(AgentTool):
    name: str = "edit_world_entry"
    description: str = "编辑项目世界书中的设定条目"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditWorldEntryInput

    async def _execute(
        self,
        title: str,
        new_title: str | None = None,
        old_content: str | None = None,
        new_content: str | None = None,
        replace_all: bool = False,
    ) -> str:
        revision_id = _require_revision_id(self._state)
        session = await create_session()
        try:
            world_info = await _get_project_world_info(session, self.project_id)
            entry = await _resolve_entry_by_title(session, world_info.id, title)
            before = _preview_from_entry(entry)
            content = entry.content
            if old_content is not None and new_content is not None:
                if old_content not in content:
                    raise ToolExecutionError("未在世界书条目内容中找到要替换的文本")
                content = (
                    content.replace(old_content, new_content)
                    if replace_all
                    else content.replace(old_content, new_content, 1)
                )
            normalized_new_title = None
            if new_title is not None:
                normalized_new_title = await _ensure_title_available(
                    session,
                    world_info.id,
                    new_title,
                    exclude_entry_id=entry.id,
                )
            before_images = world_entry_images_by_id([entry], project_id=self.project_id)
            updated = await world_info_entry_service.update_entry(
                session,
                entry.id,
                name=normalized_new_title,
                content=content if content != before.content else None,
            )
            await record_world_entry_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before_images,
                after=world_entry_images_by_id([updated], project_id=self.project_id),
            )
            await session.commit()
            after = _preview_from_entry(updated)
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "world_info_id": world_info.id,
                        "world_entry_diff": _build_world_entry_diff(before, after),
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


@ToolRegistry.register
class DeleteWorldEntryTool(AgentTool):
    name: str = "delete_world_entry"
    description: str = "删除项目世界书中指定的设定条目"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteWorldEntryInput

    async def _execute(self, title: str) -> str:
        revision_id = _require_revision_id(self._state)
        session = await create_session()
        try:
            world_info = await _get_project_world_info(session, self.project_id)
            entry = await _resolve_entry_by_title(session, world_info.id, title)
            before = _preview_from_entry(entry)
            before_images = world_entry_images_by_id([entry], project_id=self.project_id)
            await world_info_entry_service.delete_entry(session, entry.id)
            await record_world_entry_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before_images,
                after={},
            )
            await session.commit()
            return json.dumps(
                {
                    "success": True,
                    "metadata": {
                        "world_info_id": world_info.id,
                        "world_entry_diff": _build_world_entry_diff(before, None),
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
