"""Default primary and subagent definitions."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, cast

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
    enabled_tool_categories: tuple[str, ...]
    enabled_skills: tuple[str, ...]
    metadata: Mapping[str, Any]
    enabled: bool = True
    source: Literal["builtin", "custom"] = "builtin"
    color: str | None = None
    icon: str | None = None
    delegatable_agents: tuple[str, ...] = ()


DEFAULT_AGENT_KEYS: tuple[str, ...] = (
    "build",
    "plan",
    "explore",
    "composer",
    "auditor",
    "writer",
    "reviewer",
    "actor",
)


DEFAULT_AGENT_DEFINITIONS: Mapping[str, AgentDefinition] = MappingProxyType(
    {
        "build": AgentDefinition(
            key="build",
            display_name="Build",
            description=(
                "Agen bawaan yang menjalankan tugas penulisan umum "
                "dan menjadwalkan sub-agen untuk menuntaskan pekerjaan bila diperlukan"
            ),
            kind="primary",
            prompt_agent_name="build",
            model_id=None,
            enabled_tool_categories=(
                "orchestration",
                "interaction",
                "web_search",
                "web_fetch",
                "plan",
                "chapter_read",
                "chapter_write",
                "summary_read",
                "world_read",
                "world_write",
                "note_read",
                "note_write",
                "character_read",
                "character_write"
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
            color="blue",
            icon="pen-tool",
            delegatable_agents=(
                "explore",
                "composer",
                "auditor",
                "writer",
                "actor",
                "reviewer",
            ),
        ),
        "plan": AgentDefinition(
            key="plan",
            display_name="Plan",
            description=(
                "Berfokus pada perencanaan dan koordinasi: menata pekerjaan sub-agen, "
                "menelaah, dan menyerahkan hasil untuk tugas penulisan sistematis"
            ),
            kind="primary",
            prompt_agent_name="plan",
            model_id=None,
            enabled_tool_categories=(
                "orchestration",
                "interaction",
                "plan",
                "chapter_read",
                "summary_read",
                "world_read",
                "note_read",
                "character_read",
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
            color="green",
            icon="list-checks",
            delegatable_agents=(
                "explore",
                "composer",
                "auditor",
                "writer",
                "actor",
                "reviewer",
            ),
        ),
        "explore": AgentDefinition(
            key="explore",
            display_name="Explore",
            description="Menangani pengumpulan informasi, penataan konteks, dan pencarian bukti",
            kind="subagent",
            prompt_agent_name="explore",
            model_id=None,
            enabled_tool_categories=(
                "chapter_read",
                "summary_read",
                "world_read",
                "web_search",
                "web_fetch",
                "note_read",
                "character_read"
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
        ),
        "composer": AgentDefinition(
            key="composer",
            display_name="Composer",
            description="Menangani perancangan alur cerita, perencanaan struktur, dan penataan rencana penulisan",
            kind="subagent",
            prompt_agent_name="composer",
            model_id=None,
            enabled_tool_categories=(
                "chapter_read",
                "summary_read",
                "world_read",
                "world_write",
                "plan",
                "note_read",
                "note_write",
                "character_read",
                "character_write"
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
        ),
        "auditor": AgentDefinition(
            key="auditor",
            display_name="Auditor",
            description="Menelaah rencana, menghasilkan pendapat telaah, menunjukkan masalah, dan mengajukan saran perbaikan.",
            kind="subagent",
            prompt_agent_name="auditor",
            model_id=None,
            enabled_tool_categories=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan",
                "note_read",
                "character_read"
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
        ),
        "writer": AgentDefinition(
            key="writer",
            display_name="Writer",
            description="Menangani penulisan isi bab, penulisan susulan, dan perbaikan isi utama.",
            kind="subagent",
            prompt_agent_name="writer",
            model_id=None,
            enabled_tool_categories=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan",
                "chapter_write",
                "note_read",
                "note_write",
                "character_read"
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
        ),
        "actor": AgentDefinition(
            key="actor",
            display_name="Actor",
            description="Menjalankan perbaikan sesuai tujuan yang sudah ditetapkan dan menggerakkan tindakan konkret.",
            kind="subagent",
            prompt_agent_name="actor",
            model_id=None,
            enabled_tool_categories=(
                "plan",
                "chapter_read",
                "chapter_write",
                "summary_read",
                "world_read",
                "world_write",
                "note_read",
                "note_write",
                "character_read",
                "character_write"
            ),
            enabled_skills=(),
            metadata=MappingProxyType({}),
        ),
        "reviewer": AgentDefinition(
            key="reviewer",
            display_name="Reviewer",
            description="Menelaah isi penulisan, menghasilkan pendapat telaah, menunjukkan masalah, dan mengajukan saran perbaikan.",
            kind="subagent",
            prompt_agent_name="reviewer",
            model_id=None,
            enabled_tool_categories=(
                "chapter_read",
                "summary_read",
                "world_read",
                "plan",
                "character_read",
                "note_read"
            ),
            enabled_skills=(),
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
        kind=cast(Literal["primary", "subagent"], record.kind),
        prompt_agent_name=record.prompt_agent_name,
        model_id=record.model_id,
        enabled_tool_categories=tuple(record.enabled_tool_categories or ()),
        enabled_skills=tuple(record.enabled_skills or ()),
        metadata=MappingProxyType(dict(record.metadata_json or {})),
        enabled=record.enabled,
        source=cast(Literal["builtin", "custom"], record.source),
        color=record.color,
        icon=record.icon,
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
    definitions = {key: DEFAULT_AGENT_DEFINITIONS[key] for key in DEFAULT_AGENT_KEYS}
    result = await session.execute(
        select(AgentDefinitionRecord).order_by(
            col(AgentDefinitionRecord.order_index),
            col(AgentDefinitionRecord.key),
        )
    )
    for record in result.scalars():
        definitions[record.key] = agent_definition_from_record(record)
    return definitions
