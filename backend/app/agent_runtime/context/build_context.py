from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import TypeVar

from langchain_core.messages import BaseMessage
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.compaction.overlay import apply_compaction_overlay
from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.parts.history import build_history
from app.agent_runtime.context.parts.rules import build_rules
from app.agent_runtime.context.parts.skills import build_skills
from app.agent_runtime.context.parts.system_prompt import build_system_prompt
from app.agent_runtime.context.processors.compress import compress_system_prompts_if_enabled
from app.agent_runtime.context.processors.filter import (
    filter_invalid,
    filter_tool_result_metadata,
)
from app.agent_runtime.context.processors.sanitize import sanitize_surrogates
from app.agent_runtime.context.processors.to_langchain import to_langchain_messages
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.persistence import compaction_repo

T = TypeVar("T")


async def _run_read_phase(
    *,
    phase: str,
    session_id: str,
    db_session: AsyncSession,
    operation: Callable[[], Awaitable[T]],
) -> T:
    started_at = perf_counter()
    logger.info(
        "agent_context_db_phase_start session_id={} phase={}",
        session_id,
        phase,
    )
    try:
        return await operation()
    finally:
        phase_ms = int((perf_counter() - started_at) * 1000)
        rollback_started_at = perf_counter()
        await db_session.rollback()
        logger.info(
            "agent_context_db_phase_end session_id={} phase={} phase_ms={} "
            "rollback_ms={}",
            session_id,
            phase,
            phase_ms,
            int((perf_counter() - rollback_started_at) * 1000),
    )


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
    session_id = str(state.get("session_id") or "unknown")
    prompt_messages = await _run_read_phase(
        phase="system_prompt",
        session_id=session_id,
        db_session=db_session,
        operation=lambda: build_system_prompt(state, agent_name, db_session),
    )
    if prompt_messages:
        parts.extend(prompt_messages)
    rules = await _run_read_phase(
        phase="rules",
        session_id=session_id,
        db_session=db_session,
        operation=lambda: build_rules(db_session, state.get("project_id")),
    )
    if rules is not None:
        m = rules
        parts.append(m)
    skills = await _run_read_phase(
        phase="skills",
        session_id=session_id,
        db_session=db_session,
        operation=lambda: build_skills(state, agent_name, db_session, node_messages),
    )
    if skills is not None:
        m = skills
        parts.append(m)
    history_messages = await _run_read_phase(
        phase="history",
        session_id=session_id,
        db_session=db_session,
        operation=lambda: build_history(node_messages, db_session),
    )
    parts.extend(history_messages)

    cleaned = _process(parts)
    static = [m for m in cleaned if not _is_history(m)]
    history = [m for m in cleaned if _is_history(m)]
    try:
        compactions = await _run_read_phase(
            phase="compactions",
            session_id=session_id,
            db_session=db_session,
            operation=lambda: compaction_repo.list_by_session(
                db_session, state["session_id"]
            ),
        )
    except Exception as e:
        raise ContextBuildError(
            "compaction",
            "failed to load compactions",
            cause=e,
        ) from e
    overlaid_history = apply_compaction_overlay(history, compactions)
    result = static + overlaid_history
    result = await _run_read_phase(
        phase="compress_system_prompts",
        session_id=session_id,
        db_session=db_session,
        operation=lambda: compress_system_prompts_if_enabled(result, db_session),
    )
    return result


def _is_history(message: ContextMessage) -> bool:
    return (message.metadata or {}).get("part") == "history"


def _process(parts: list[ContextMessage]) -> list[ContextMessage]:
    parts = filter_invalid(parts)
    parts = sanitize_surrogates(parts)
    return filter_tool_result_metadata(parts)
