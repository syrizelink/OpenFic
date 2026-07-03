"""Default PA/SA agent definitions."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.model import AgentDefinitionRecord


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    display_name: str
    description: str
    kind: Literal["primary", "subagent"]
    prompt_agent_name: str
    model_id: str | None
    tool_category_keys: tuple[str, ...]
    enabled_skill_ids: tuple[str, ...]
    metadata: Mapping[str, Any]
    enabled: bool = True
    source: Literal["builtin", "custom"] = "builtin"
    delegatable_agents: tuple[str, ...] = ()


DEFAULT_AGENT_KEYS: tuple[str, ...] = (
    "primary",
    "explorer",
    "composer",
    "auditor",
    "writer",
    "actor",
    "reviewer",
)


DEFAULT_AGENT_DEFINITIONS: Mapping[str, AgentDefinition] = MappingProxyType(
    {
        "primary": AgentDefinition(
            key="primary",
            display_name="Orchestrator",
            description="负责任务拆解、调度子智能体并整合最终结果。",
            kind="primary",
            prompt_agent_name="primary",
            model_id=None,
            tool_category_keys=(
                "orchestration",
                "interaction",
                "plan_read",
                "plan_write",
                "chapter_read",
                "chapter_write",
                "summary_read",
                "world_read",
                "world_write",
                "note_read",
                "note_write",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
        "explorer": AgentDefinition(
            key="explorer",
            display_name="Explorer",
            description="负责信息搜集、上下文梳理与证据查找",
            kind="subagent",
            prompt_agent_name="explorer",
            model_id=None,
            tool_category_keys=(
                "chapter_read",
                "summary_read",
                "world_read",
                "note_read",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
        "composer": AgentDefinition(
            key="composer",
            display_name="Composer",
            description="负责剧情设计、结构规划与写作方案的组织",
            kind="subagent",
            prompt_agent_name="composer",
            model_id=None,
            tool_category_keys=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan_read",
                "note_read",
                "note_write",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
        "auditor": AgentDefinition(
            key="auditor",
            display_name="Auditor",
            description="负责审查计划，产出评审意见、指出问题并提出修正建议。",
            kind="subagent",
            prompt_agent_name="auditor",
            model_id=None,
            tool_category_keys=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan_read",
                "note_read",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
        "writer": AgentDefinition(
            key="writer",
            display_name="Writer",
            description="负责章节内容撰写、补写与正文修改。",
            kind="subagent",
            prompt_agent_name="writer",
            model_id=None,
            tool_category_keys=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan_read",
                "chapter_write",
                "note_read",
                "note_write",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
        "actor": AgentDefinition(
            key="actor",
            display_name="Actor",
            description="负责按既定目标执行修改并推进具体动作。",
            kind="subagent",
            prompt_agent_name="actor",
            model_id=None,
            tool_category_keys=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan_read",
                "chapter_write",
                "note_read",
                "note_write",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
        "reviewer": AgentDefinition(
            key="reviewer",
            display_name="Reviewer",
            description="负责审查写作内容，产出评审意见、指出问题并提出修正建议。",
            kind="subagent",
            prompt_agent_name="reviewer",
            model_id=None,
            tool_category_keys=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan_read",
            ),
            enabled_skill_ids=(),
            metadata=MappingProxyType({}),
        ),
    }
)


def get_default_agent_definition(key: str) -> AgentDefinition:
    return DEFAULT_AGENT_DEFINITIONS[key]


def agent_definition_from_record(record: AgentDefinitionRecord) -> AgentDefinition:
    return AgentDefinition(
        key=record.key,
        display_name=record.display_name,
        description=record.description,
        kind=record.kind,  # type: ignore[arg-type]
        prompt_agent_name=record.prompt_agent_name,
        model_id=record.model_id,
        tool_category_keys=tuple(record.tool_category_keys_json or ()),
        enabled_skill_ids=tuple(record.enabled_skill_ids_json or ()),
        metadata=MappingProxyType(dict(record.metadata_json or {})),
        enabled=record.enabled,
        source=record.source,  # type: ignore[arg-type]
        delegatable_agents=tuple(record.delegatable_agents or ()),
    )


async def load_agent_definition(
    session: AsyncSession,
    key: str,
) -> AgentDefinition:
    result = await session.execute(
        select(AgentDefinitionRecord).where(col(AgentDefinitionRecord.key) == key)
    )
    record = result.scalar_one_or_none()
    if record is not None:
        return agent_definition_from_record(record)
    return get_default_agent_definition(key)


async def load_all_agent_definitions(
    session: AsyncSession,
) -> dict[str, AgentDefinition]:
    definitions = dict(DEFAULT_AGENT_DEFINITIONS)
    result = await session.execute(
        select(AgentDefinitionRecord).order_by(
            col(AgentDefinitionRecord.order_index),
            col(AgentDefinitionRecord.key),
        )
    )
    for record in result.scalars():
        definitions[record.key] = agent_definition_from_record(record)
    return definitions
