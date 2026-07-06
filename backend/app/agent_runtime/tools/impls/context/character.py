import json
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.revisions import (
    character_images_by_id,
    current_revision_id_from_state,
    record_character_diffs,
)
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.models.character import Character
from app.storage.repos import character_repo
from app.storage.services import character_service


class ListCharactersInput(BaseModel):
    pass


class ReadCharacterInput(BaseModel):
    name: str = Field(description="要读取的角色名称")


class CreateCharacterInput(BaseModel):
    name: str = Field(description="新角色名称")
    description: str = Field(description="新角色描述")


class EditCharacterInput(BaseModel):
    name: str = Field(description="要编辑的角色名称")
    new_name: str | None = Field(default=None, description="可选的新角色名称")
    old_description: str | None = Field(default=None, description="要查找并替换的原始描述文本")
    new_description: str | None = Field(default=None, description="用于替换 old_description 的新描述文本")
    replace_all: bool = Field(default=False, description="是否替换命中的全部 old_description")

    @field_validator("new_description", mode="after")
    @classmethod
    def check_edit_fields(cls, v, info):
        data = info.data
        has_name = data.get("new_name") is not None
        has_description = data.get("old_description") is not None and v is not None
        if not has_name and not has_description:
            raise ValueError("new_name 和 old_description/new_description 必填一类")
        return v


class DeleteCharacterInput(BaseModel):
    name: str = Field(description="要删除的角色名称")


@dataclass(frozen=True)
class CharacterPreview:
    id: str
    name: str
    description: str


def _serialize_character(character: Character) -> dict:
    return {
        "id": character.id,
        "name": character.name,
        "description": character.description,
    }


def _preview_from_character(character: Character) -> CharacterPreview:
    return CharacterPreview(
        id=character.id,
        name=character.name,
        description=character.description,
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


def _build_character_diff(
    before: CharacterPreview | None,
    after: CharacterPreview | None,
) -> dict:
    target = after or before
    if target is None:
        raise ToolExecutionError("缺少角色 diff 数据")
    if before is None:
        operation = "create"
        lines = _diff_lines(None, after.description if after else "")
    elif after is None:
        operation = "delete"
        lines = _diff_lines(before.description, None)
    else:
        operation = "edit"
        lines = _diff_lines(before.description, after.description) if before.description != after.description else []
    return {
        "operation": operation,
        "character_id": target.id,
        "character_name": target.name,
        "sections": [{"type": "content", "lines": lines}],
    }


async def _list_project_characters(session, project_id: str) -> list[Character]:
    characters, _ = await character_repo.list_by_project(
        session, project_id, page=1, page_size=10000
    )
    return characters


async def _resolve_character_by_name(session, project_id: str, name: str) -> Character:
    normalized_name = name.strip()
    if not normalized_name:
        raise ToolExecutionError("角色名称不能为空")
    characters = await _list_project_characters(session, project_id)
    matches = [character for character in characters if character.name == normalized_name]
    if not matches:
        raise ToolExecutionError(f"角色不存在: {normalized_name}")
    if len(matches) > 1:
        raise ToolExecutionError(f"角色名称不唯一: {normalized_name}")
    return matches[0]


async def _ensure_name_available(
    session,
    project_id: str,
    name: str,
    exclude_character_id: str | None = None,
) -> str:
    normalized_name = name.strip()
    if not normalized_name:
        raise ToolExecutionError("角色名称不能为空")
    characters = await _list_project_characters(session, project_id)
    if any(
        character.name == normalized_name and character.id != exclude_character_id
        for character in characters
    ):
        raise ToolExecutionError(f"角色名称已存在: {normalized_name}")
    return normalized_name


def _require_revision_id(state: dict) -> str:
    revision_id = current_revision_id_from_state(state)
    if revision_id is None:
        raise ToolExecutionError("缺少当前 revision，无法执行角色修改")
    return revision_id


@ToolRegistry.register
class ListCharactersTool(AgentTool):
    name: str = "list_characters"
    description: str = "获取当前项目中的角色名称列表。"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListCharactersInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            characters = await _list_project_characters(session, self.project_id)
            return json.dumps(
                {
                    "characters": [
                        {"name": character.name}
                        for character in characters
                    ]
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()


@ToolRegistry.register
class ReadCharacterTool(AgentTool):
    name: str = "read_character"
    description: str = "根据名称读取当前项目中的单个角色描述。"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadCharacterInput

    async def _execute(self, name: str) -> str:
        session = await create_session()
        try:
            character = await _resolve_character_by_name(session, self.project_id, name)
            return json.dumps(
                {
                    "name": character.name,
                    "description": _format_content_with_line_numbers(character.description),
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()


@ToolRegistry.register
class CreateCharacterTool(AgentTool):
    name: str = "create_character"
    description: str = "在当前项目中创建角色。"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateCharacterInput

    async def _execute(self, name: str, description: str) -> str:
        revision_id = _require_revision_id(self._state)
        session = await create_session()
        try:
            normalized_name = await _ensure_name_available(session, self.project_id, name)
            character = await character_service.create_character(
                session,
                self.project_id,
                name=normalized_name,
                description=description,
            )
            affected_characters = await record_character_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before={},
                after=character_images_by_id([character]),
            )
            await session.commit()
            character_preview = _preview_from_character(character)
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": revision_id,
                    "affected_characters": affected_characters,
                    "character": _serialize_character(character),
                    "character_diff": _build_character_diff(None, character_preview),
                    "message": "角色已创建",
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@ToolRegistry.register
class EditCharacterTool(AgentTool):
    name: str = "edit_character"
    description: str = "编辑当前项目角色的名称或描述。修改描述时使用查找替换模式。"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditCharacterInput

    async def _execute(
        self,
        name: str,
        new_name: str | None = None,
        old_description: str | None = None,
        new_description: str | None = None,
        replace_all: bool = False,
    ) -> str:
        revision_id = _require_revision_id(self._state)
        session = await create_session()
        try:
            character = await _resolve_character_by_name(session, self.project_id, name)
            before = _preview_from_character(character)
            description = character.description
            if old_description is not None and new_description is not None:
                if old_description not in description:
                    raise ToolExecutionError("未在角色描述中找到要替换的文本")
                description = (
                    description.replace(old_description, new_description)
                    if replace_all
                    else description.replace(old_description, new_description, 1)
                )
            normalized_new_name = None
            if new_name is not None:
                normalized_new_name = await _ensure_name_available(
                    session,
                    self.project_id,
                    new_name,
                    exclude_character_id=character.id,
                )
            before_images = character_images_by_id([character])
            updated = await character_service.update_character(
                session,
                character.id,
                name=normalized_new_name,
                description=description if description != before.description else None,
            )
            affected_characters = await record_character_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before_images,
                after=character_images_by_id([updated]),
            )
            await session.commit()
            after = _preview_from_character(updated)
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": revision_id,
                    "affected_characters": affected_characters,
                    "character": _serialize_character(updated),
                    "character_diff": _build_character_diff(before, after),
                    "message": "角色已编辑",
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
class DeleteCharacterTool(AgentTool):
    name: str = "delete_character"
    description: str = "根据名称删除当前项目中的单个角色。"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteCharacterInput

    async def _execute(self, name: str) -> str:
        revision_id = _require_revision_id(self._state)
        session = await create_session()
        try:
            character = await _resolve_character_by_name(session, self.project_id, name)
            before = _preview_from_character(character)
            before_images = character_images_by_id([character])
            await character_service.delete_character(session, character.id)
            affected_characters = await record_character_diffs(
                session,
                revision_id=revision_id,
                project_id=self.project_id,
                before=before_images,
                after={},
            )
            await session.commit()
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": revision_id,
                    "affected_characters": affected_characters,
                    "character_id": before.id,
                    "name": before.name,
                    "message": "角色已删除",
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
