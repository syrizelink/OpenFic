from collections.abc import Iterable
import html
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import load_agent_definition
from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.helpers import extract_referenced_skill_ids
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.storage.services import skill_service


async def _get_enabled_skill_ids_for_agent(
    db_session: AsyncSession,
    agent_name: str,
) -> list[str]:
    try:
        definition = await load_agent_definition(db_session, agent_name)
    except KeyError:
        return []
    return [skill_id for skill_id in definition.enabled_skills if skill_id]


async def build_skills(
    state: AgentRuntimeState,
    agent_name: str,
    db_session: AsyncSession,
    node_messages: list[dict] | None = None,
) -> ContextMessage | None:
    """构建 Skills 上下文片段：列出 agent 可用技能的名称与简介。"""

    enabled_skill_ids = await _get_enabled_skill_ids_for_agent(db_session, agent_name)
    existing_referenced_ids = _state_skill_ids(state)
    node_message_texts = tuple(_node_user_message_texts(node_messages))
    current_request = state.get("user_request")
    user_message_texts = (
        tuple(text for text in node_message_texts if text != current_request)
        if existing_referenced_ids
        else tuple(_user_message_texts(state, node_messages))
    )
    has_skill_references = any(
        "<of-skill" in text for text in user_message_texts
    ) or bool(existing_referenced_ids)

    try:
        agent_skills = await skill_service.list_enabled_skills_by_ids(
            db_session,
            enabled_skill_ids,
        )
        globally_enabled = (
            await skill_service.list_enabled_skills(db_session) if has_skill_references else []
        )
    except Exception as e:
        raise ContextBuildError("skills", "failed to load enabled skills", cause=e) from e

    referenced_ids = _merge_unique(
        existing_referenced_ids,
        extract_referenced_skill_ids(user_message_texts),
    )
    if isinstance(state, dict):
        state["referenced_skill_ids"] = list(referenced_ids)

    agent_skill_ids = {skill.id for skill in agent_skills}
    referenced_skills = [
        skill
        for skill in globally_enabled
        if skill.id in referenced_ids and skill.id not in agent_skill_ids
    ]
    available = [*agent_skills, *referenced_skills]

    if not available:
        return None

    skill_blocks = "\n".join(
        f"<skill>\n  <name>{html.escape(skill.name.strip())}</name>\n"
        f"  <description>{html.escape(skill.summary)}</description>\n</skill>"
        for skill in available
    )
    content = (
        "<available_skills>\n"
        "The following skills provide specialized instructions for specific tasks.\n"
        "When a task matches a skill's description, call the activate_skill tool with the skill's name to load its full instructions.\n"
        f"{skill_blocks}\n"
        "</available_skills>"
    )

    return ContextMessage(
        role="system",
        content=content,
        metadata={"part": "skills"},
    )


def _state_skill_ids(state: AgentRuntimeState) -> tuple[str, ...]:
    values = state.get("referenced_skill_ids")
    if not isinstance(values, (list, tuple, set)):
        return ()
    return _merge_unique(value for value in values if isinstance(value, str))


def _merge_unique(*groups: Iterable[str]) -> tuple[str, ...]:
    values: list[str] = []
    for group in groups:
        for value in group:
            normalized = value.strip()
            if normalized and normalized not in values:
                values.append(normalized)
    return tuple(values)


def _node_user_message_texts(node_messages: list[dict] | None) -> Iterable[str]:
    for raw in node_messages or []:
        if not isinstance(raw, dict) or raw.get("role") != "user":
            continue
        content: Any = raw.get("content")
        if isinstance(content, str) and content:
            yield content


def _user_message_texts(
    state: AgentRuntimeState,
    node_messages: list[dict] | None,
) -> Iterable[str]:
    user_request = state.get("user_request")
    if isinstance(user_request, str) and user_request:
        yield user_request
    yield from _node_user_message_texts(node_messages)
