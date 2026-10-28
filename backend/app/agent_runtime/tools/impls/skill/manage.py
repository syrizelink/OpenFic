"""Agent tools for managing disabled custom skills and their references."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls._locks import keyed_lock
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.errors import ConflictError, NotFoundError
from app.storage.database import create_session
from app.storage.models.skill import Skill
from app.storage.services import skill_reference_doc_service, skill_service


class SkillManagementInput(BaseModel):
    # In particular, never silently accept an is_enabled or references argument.
    model_config = ConfigDict(extra="forbid")


class ListSkillsInput(SkillManagementInput):
    pass


class GetSkillInput(SkillManagementInput):
    skill_id: str = Field(description="要查看的 Skill ID")


class GetSkillReferenceDocInput(SkillManagementInput):
    skill_id: str = Field(description="所属 Skill ID")
    doc_id: str = Field(description="参考文档 ID")


class CreateSkillInput(SkillManagementInput):
    name: str = Field(description="技能名称", max_length=200)
    summary: str = Field(description="技能简述")
    content: str = Field(description="技能内容")


class EditSkillInput(SkillManagementInput):
    skill_id: str = Field(description="要修改的 Skill ID，必须为关闭的自定义 Skill")
    name: str | None = Field(default=None, description="新名称", max_length=200)
    summary: str | None = Field(default=None, description="新简述")
    content: str | None = Field(default=None, description="新的完整技能内容")

    @model_validator(mode="after")
    def check_changes(self):
        if self.name is None and self.summary is None and self.content is None:
            raise ValueError("至少提供一个要修改的字段")
        return self


class CreateSkillReferenceDocInput(SkillManagementInput):
    skill_id: str = Field(description="所属 Skill ID，必须为关闭的自定义 Skill")
    title: str = Field(description="参考文档标题", max_length=200)
    content: str = Field(description="参考文档内容")


class EditSkillReferenceDocInput(SkillManagementInput):
    skill_id: str = Field(description="所属 Skill ID，必须为关闭的自定义 Skill")
    doc_id: str = Field(description="参考文档 ID")
    title: str | None = Field(default=None, description="新标题", max_length=200)
    content: str | None = Field(default=None, description="新的完整参考文档内容")

    @model_validator(mode="after")
    def check_changes(self):
        if self.title is None and self.content is None:
            raise ValueError("至少提供一个要修改的字段")
        return self


class DeleteSkillInput(SkillManagementInput):
    skill_id: str = Field(description="要删除的 Skill ID，必须为关闭的自定义 Skill")


class DeleteSkillReferenceDocInput(SkillManagementInput):
    skill_id: str = Field(description="所属 Skill ID，必须为关闭的自定义 Skill")
    doc_id: str = Field(description="要删除的参考文档 ID")


def _skill_data(skill: skill_service.SkillData) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "summary": skill.summary,
        "content": skill.content,
        "is_enabled": skill.is_enabled,
        "is_complete": skill_service.is_skill_complete(skill),
        "source": skill.source,
    }


def _reference_data(doc: skill_service.SkillReferenceData) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "tokens": doc.tokens,
    }


async def _require_editable_skill(session: AsyncSession, skill_id: str) -> None:
    skill = await skill_service.get_skill(session, skill_id)
    if skill_service.is_builtin_skill(skill):
        raise ToolExecutionError(
            f"不可编辑内置 Skill: {skill_id}", code="permission_denied"
        )
    if skill.is_enabled:
        raise ToolExecutionError(
            f"不可编辑已启用的 Skill: {skill_id}", code="permission_denied"
        )
    # Claim the row only while it is disabled. This also prevents an enable
    # operation in another transaction from racing the subsequent edit.
    result = await session.execute(
        update(Skill)
        .where(col(Skill.id) == skill_id, col(Skill.is_enabled).is_(False))
        .values(updated_at=col(Skill.updated_at))
        .execution_options(synchronize_session=False)
    )
    if cast(CursorResult, result).rowcount != 1:
        raise ToolExecutionError(
            f"Skill 已启用或不存在，无法编辑: {skill_id}", code="permission_denied"
        )


@asynccontextmanager
async def _write_session() -> AsyncIterator[AsyncSession]:
    # Skills are global rather than project-scoped; serialize agent writes globally.
    async with await keyed_lock("skill_management"):
        session = await create_session()
        try:
            yield session
            await session.commit()
        except (
            NotFoundError,
            ConflictError,
            skill_service.SkillValidationError,
        ) as exc:
            await session.rollback()
            code = (
                "not_found"
                if isinstance(exc, NotFoundError)
                else "conflict"
                if isinstance(exc, ConflictError)
                else "validation_error"
            )
            raise ToolExecutionError(str(exc), code=code) from exc
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@ToolRegistry.register
class ListSkillsTool(AgentTool):
    name: str = "list_skills"
    description: str = (
        "列出全部内置和自定义 Skill，包括启用状态。关闭的自定义 Skill 还会返回完整内容"
        "及参考文档，使用返回的 ID 可编辑；其他 Skill 请通过已授权的技能工具读取。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListSkillsInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            items = []
            page = 1
            while True:
                result = await skill_service.list_skills(
                    session, page=page, page_size=100
                )
                for skill in result.items:
                    item = _skill_data(skill)
                    editable = skill.source == "custom" and not skill.is_enabled
                    item["editable"] = editable
                    if editable:
                        item["reference_docs"] = [
                            _reference_data(doc)
                            for doc in await skill_service.list_reference_docs(
                                session, skill.id
                            )
                        ]
                    else:
                        del item["content"]
                    items.append(item)
                if len(items) >= result.total or not result.items:
                    break
                page += 1
            return json.dumps(
                {"skills": items, "total": len(items)}, ensure_ascii=False
            )
        finally:
            await session.close()


@ToolRegistry.register
class GetSkillTool(AgentTool):
    name: str = "get_skill"
    description: str = (
        "查看指定 Skill 的完整信息和参考文档；这是 Skill 管理工具，不受当前 Agent 的启用/挂载范围限制。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = GetSkillInput

    async def _execute(self, skill_id: str) -> str:
        session = await create_session()
        try:
            skill = await skill_service.get_skill(session, skill_id)
            result = _skill_data(skill)
            result["reference_docs"] = [
                _reference_data(doc)
                for doc in await skill_service.list_reference_docs(session, skill.id)
            ]
        finally:
            await session.close()
        return json.dumps({"skill": result}, ensure_ascii=False)


@ToolRegistry.register
class GetSkillReferenceDocTool(AgentTool):
    name: str = "get_skill_reference_doc"
    description: str = (
        "查看指定 Skill 的完整参考文档；这是 Skill 管理工具，不受当前 Agent 的启用/挂载范围限制。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = GetSkillReferenceDocInput

    async def _execute(self, skill_id: str, doc_id: str) -> str:
        session = await create_session()
        try:
            await skill_service.get_skill(session, skill_id)
            docs = await skill_service.list_reference_docs(session, skill_id)
            doc = next((item for item in docs if item.id == doc_id), None)
            if doc is None:
                raise NotFoundError(f"指定 Skill 中不存在参考文档: {doc_id}")
            result = _reference_data(doc)
        finally:
            await session.close()
        return json.dumps(
            {"skill_id": skill_id, "reference_doc": result}, ensure_ascii=False
        )


@ToolRegistry.register
class CreateSkillTool(AgentTool):
    name: str = "create_skill"
    description: str = (
        "创建自定义 Skill；新 Skill 默认关闭，且不含参考文档，也不会关联到任何 Agent。"
    )
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateSkillInput

    async def _execute(self, name: str, summary: str, content: str) -> str:
        async with _write_session() as session:
            skill = await skill_service.create_skill(
                session, name=name, summary=summary, content=content, is_enabled=False
            )
            result = _skill_data(skill)
            result["reference_docs"] = []
        return json.dumps({"success": True, "skill": result}, ensure_ascii=False)


@ToolRegistry.register
class EditSkillTool(AgentTool):
    name: str = "edit_skill"
    description: str = (
        "编辑关闭的自定义 Skill 的名称、简述或完整内容；不能修改开关状态。"
    )
    access_level: str = "write"
    args_schema: type[BaseModel] = EditSkillInput

    async def _execute(
        self,
        skill_id: str,
        name: str | None = None,
        summary: str | None = None,
        content: str | None = None,
    ) -> str:
        async with _write_session() as session:
            await _require_editable_skill(session, skill_id)
            skill = await skill_service.update_skill(
                session, skill_id, name=name, summary=summary, content=content
            )
            result = _skill_data(skill)
        return json.dumps({"success": True, "skill": result}, ensure_ascii=False)


@ToolRegistry.register
class CreateSkillReferenceDocTool(AgentTool):
    name: str = "create_skill_reference_doc"
    description: str = "为关闭的自定义 Skill 创建参考文档。"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateSkillReferenceDocInput

    async def _execute(self, skill_id: str, title: str, content: str) -> str:
        async with _write_session() as session:
            await _require_editable_skill(session, skill_id)
            doc = await skill_reference_doc_service.create_reference_doc(
                session, skill_id, title=title, content=content
            )
            result = _reference_data(doc)
        return json.dumps(
            {"success": True, "skill_id": skill_id, "reference_doc": result},
            ensure_ascii=False,
        )


@ToolRegistry.register
class EditSkillReferenceDocTool(AgentTool):
    name: str = "edit_skill_reference_doc"
    description: str = "编辑关闭的自定义 Skill 的参考文档标题或完整内容。"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditSkillReferenceDocInput

    async def _execute(
        self,
        skill_id: str,
        doc_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> str:
        async with _write_session() as session:
            await _require_editable_skill(session, skill_id)
            doc = await skill_reference_doc_service.update_reference_doc(
                session, skill_id, doc_id, title=title, content=content
            )
            result = _reference_data(doc)
        return json.dumps(
            {"success": True, "skill_id": skill_id, "reference_doc": result},
            ensure_ascii=False,
        )


@ToolRegistry.register
class DeleteSkillTool(AgentTool):
    name: str = "delete_skill"
    description: str = "删除关闭的自定义 Skill 及其全部参考文档；不能删除内置或已启用 Skill。"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteSkillInput

    async def _execute(self, skill_id: str) -> str:
        async with _write_session() as session:
            await _require_editable_skill(session, skill_id)
            await skill_service.delete_skill(session, skill_id)
        return json.dumps({"success": True, "skill_id": skill_id}, ensure_ascii=False)


@ToolRegistry.register
class DeleteSkillReferenceDocTool(AgentTool):
    name: str = "delete_skill_reference_doc"
    description: str = "删除关闭的自定义 Skill 的参考文档；不能删除内置或已启用 Skill 的参考文档。"
    access_level: str = "write"
    args_schema: type[BaseModel] = DeleteSkillReferenceDocInput

    async def _execute(self, skill_id: str, doc_id: str) -> str:
        async with _write_session() as session:
            await _require_editable_skill(session, skill_id)
            await skill_reference_doc_service.delete_reference_doc(session, skill_id, doc_id)
        return json.dumps(
            {"success": True, "skill_id": skill_id, "doc_id": doc_id},
            ensure_ascii=False,
        )
