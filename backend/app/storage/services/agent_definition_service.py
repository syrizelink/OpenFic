# -*- coding: utf-8 -*-
"""
AgentDefinition Service - Business logic for agent definitions CRUD.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import (
    AgentDefinition,
    agent_definition_from_record,
    get_default_agent_definition,
    load_agent_definition,
)
from app.agent_runtime.persistence.model import AgentDefinitionRecord
from app.core.errors import NotFoundError, ValidationError
from app.storage.repos import agent_definition_repo

_BUILTIN_KEYS = frozenset(
    ("primary", "explorer", "composer", "auditor", "writer", "actor", "reviewer")
)
_SUBAGENT_RESTRICTED_TOOL_CATEGORIES = frozenset(("orchestration", "interaction"))


def _normalize_enabled_skills(skill_ids: list[str] | None) -> list[str]:
    if not skill_ids:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for skill_id in skill_ids:
        value = skill_id.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _normalize_enabled_tool_categories(
    kind: str,
    category_keys: list[str],
) -> list[str]:
    if kind != "subagent":
        return category_keys
    return [
        category_key
        for category_key in category_keys
        if category_key not in _SUBAGENT_RESTRICTED_TOOL_CATEGORIES
    ]


def _normalize_delegatable_agents(
    kind: str,
    agent_keys: list[str] | None,
) -> list[str]:
    if kind != "primary":
        return []
    return agent_keys or []


async def list_definitions(
    session: AsyncSession,
) -> list[AgentDefinition]:
    merged: dict[str, AgentDefinition] = {}

    for key in _BUILTIN_KEYS:
        merged[key] = get_default_agent_definition(key)

    records = await agent_definition_repo.list_all(session)
    for record in records:
        merged[record.key] = agent_definition_from_record(record)

    return list(merged.values())


async def get_definition(
    session: AsyncSession,
    key: str,
) -> AgentDefinition:
    return await load_agent_definition(session, key)


async def create_definition(
    session: AsyncSession,
    key: str,
    display_name: str,
    description: str,
    kind: str,
    prompt_agent_name: str,
    model_id: str | None,
    enabled_tool_categories: list[str],
    enabled_skills: list[str],
    metadata: dict[str, Any] | None,
    delegatable_agents: list[str] | None,
) -> AgentDefinitionRecord:
    existing = await agent_definition_repo.get_by_key(session, key)
    if existing is not None:
        raise ValidationError(f"智能体 {key} 已存在")

    normalized_enabled_skills = _normalize_enabled_skills(enabled_skills)
    normalized_tool_categories = _normalize_enabled_tool_categories(
        kind,
        enabled_tool_categories,
    )

    record = AgentDefinitionRecord(
        key=key,
        display_name=display_name,
        description=description,
        kind=kind,
        prompt_agent_name=prompt_agent_name,
        model_id=model_id,
        enabled_tool_categories=normalized_tool_categories,
        enabled_skills=normalized_enabled_skills,
        metadata_json=metadata or {},
        enabled=True,
        source="custom",
        delegatable_agents=_normalize_delegatable_agents(kind, delegatable_agents),
    )
    return await agent_definition_repo.create(session, record)


def _build_record(
    key: str,
    default: AgentDefinition,
) -> AgentDefinitionRecord:
    return AgentDefinitionRecord(
        key=key,
        display_name=default.display_name,
        description=default.description,
        kind=default.kind,
        prompt_agent_name=default.prompt_agent_name,
        model_id=default.model_id,
        enabled_tool_categories=list(default.enabled_tool_categories),
        enabled_skills=list(default.enabled_skills),
        metadata_json=dict(default.metadata),
        enabled=default.enabled,
        source="builtin",
        delegatable_agents=list(default.delegatable_agents),
    )


async def update_definition(
    session: AsyncSession,
    key: str,
    display_name: str | None = None,
    description: str | None = None,
    kind: str | None = None,
    prompt_agent_name: str | None = None,
    model_id: str | None = None,
    enabled_tool_categories: list[str] | None = None,
    enabled_skills: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    enabled: bool | None = None,
    delegatable_agents: list[str] | None = None,
) -> AgentDefinitionRecord:
    if kind is not None and key in _BUILTIN_KEYS:
        default = get_default_agent_definition(key)
        if kind != default.kind:
            raise ValidationError(f"内置智能体类型不可修改: {key}")

    record = await agent_definition_repo.get_by_key(session, key)
    if record is None:
        try:
            default = get_default_agent_definition(key)
        except KeyError:
            raise NotFoundError(f"智能体定义不存在: {key}")
        record = _build_record(key, default)

    if display_name is not None:
        record.display_name = display_name
    if description is not None:
        record.description = description
    if kind is not None:
        record.kind = kind
    if prompt_agent_name is not None:
        record.prompt_agent_name = prompt_agent_name
    if model_id is not None:
        record.model_id = model_id
    if enabled_tool_categories is not None:
        record.enabled_tool_categories = _normalize_enabled_tool_categories(
            record.kind,
            enabled_tool_categories,
        )
    if enabled_skills is not None:
        record.enabled_skills = _normalize_enabled_skills(enabled_skills)
    if metadata is not None:
        record.metadata_json = metadata
    if enabled is not None:
        record.enabled = enabled
    if delegatable_agents is not None:
        record.delegatable_agents = _normalize_delegatable_agents(
            record.kind,
            delegatable_agents,
        )

    record.enabled_tool_categories = _normalize_enabled_tool_categories(
        record.kind,
        record.enabled_tool_categories or [],
    )
    record.delegatable_agents = _normalize_delegatable_agents(
        record.kind,
        record.delegatable_agents,
    )

    return await agent_definition_repo.update(session, record)


async def reset_definition(
    session: AsyncSession,
    key: str,
) -> AgentDefinition:
    if key not in _BUILTIN_KEYS:
        raise ValidationError(f"只有内置智能体可以重置: {key}")

    record = await agent_definition_repo.get_by_key(session, key)
    if record is not None:
        await agent_definition_repo.delete_by_key(session, key)

    from app.storage.services import prompt_chain_service

    await prompt_chain_service.delete_prompt_chain(session, f"builtin-agent--{key}")

    return get_default_agent_definition(key)


async def _remove_delegatable_reference(
    session: AsyncSession,
    removed_key: str,
) -> None:
    primaries = await agent_definition_repo.list_all(session)
    for record in primaries:
        agents = list(record.delegatable_agents or [])
        if removed_key in agents:
            agents = [a for a in agents if a != removed_key]
            record.delegatable_agents = agents
            await agent_definition_repo.update(session, record)


async def delete_definition(
    session: AsyncSession,
    key: str,
) -> None:
    if key in _BUILTIN_KEYS:
        raise ValidationError(f"不可删除内置智能体: {key}")

    record = await agent_definition_repo.get_by_key(session, key)
    if record is None:
        raise NotFoundError(f"智能体定义不存在: {key}")

    await _remove_delegatable_reference(session, key)

    await agent_definition_repo.delete_by_key(session, key)

    from app.storage.services import prompt_chain_service

    await prompt_chain_service.delete_prompt_chain(session, f"custom-agent--{key}")
