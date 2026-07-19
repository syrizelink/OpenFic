from langchain_core.messages import BaseMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.compaction.overlay import apply_compaction_overlay
from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.parts.history import build_history
from app.agent_runtime.context.parts.rules import build_rules
from app.agent_runtime.context.parts.skills import build_skills
from app.agent_runtime.context.parts.system_prompt import build_system_prompt
from app.agent_runtime.context.processors.filter import (
    filter_invalid,
    filter_tool_result_metadata,
)
from app.agent_runtime.context.processors.sanitize import sanitize_surrogates
from app.agent_runtime.context.processors.to_langchain import to_langchain_messages
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.persistence import compaction_repo


async def build_context(
    state: AgentRuntimeState,
    agent_name: str,
    node_messages: list[dict],
    db_session: AsyncSession,
) -> list[BaseMessage]:
    """组装最终发往 LLM 的消息列表。"""
    parts = await build_context_parts(state, agent_name, node_messages, db_session)
    return to_langchain_messages(parts)


async def build_context_parts(
    state: AgentRuntimeState,
    agent_name: str,
    node_messages: list[dict],
    db_session: AsyncSession,
) -> list[ContextMessage]:
    """组装经过清洗和 compaction overlay 的 ContextMessage 列表。"""
    if state["model_config"].get("max_context_tokens") is None:
        raise ContextBuildError("config", "missing max_context_tokens in model_config")

    parts: list[ContextMessage] = []
    if prompt_messages := await build_system_prompt(state, agent_name, db_session):
        parts.extend(prompt_messages)
    if (m := await build_rules(db_session)) is not None:
        parts.append(m)
    if (m := await build_skills(state, agent_name, db_session)) is not None:
        parts.append(m)
    parts.extend(await build_history(node_messages, db_session))

    cleaned = _process(parts)
    static = [m for m in cleaned if not _is_history(m)]
    history = [m for m in cleaned if _is_history(m)]
    try:
        compactions = await compaction_repo.list_by_session(db_session, state["session_id"])
    except Exception as e:
        raise ContextBuildError(
            "compaction",
            "failed to load compactions",
            cause=e,
        ) from e
    overlaid_history = apply_compaction_overlay(history, compactions)
    return static + overlaid_history


def _is_history(message: ContextMessage) -> bool:
    return (message.metadata or {}).get("part") == "history"


def _process(parts: list[ContextMessage]) -> list[ContextMessage]:
    parts = filter_invalid(parts)
    parts = sanitize_surrogates(parts)
    return filter_tool_result_metadata(parts)
