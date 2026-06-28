from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig
from loguru import logger

from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.child_runs import (
    get_child_run_agent_number,
    get_child_run_for_parent,
)
from app.agent_runtime.persistence.model import AgentChildRun, AgentChildRunRequest
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.agent_runtime.tools.errors import ToolExecutionError
from app.socket import emit
from app.socket.handlers import agent_subagent_session_room
from app.storage.database import create_session


POLL_INTERVAL_SECONDS = 0.1
_CHILD_PROCESS_FAILURES: dict[tuple[str, str], str] = {}
_CHILD_PROCESS_FAILURES_LOCK = asyncio.Lock()


@dataclass
class ChildRequestResolution:
    child_run: AgentChildRun
    request: AgentChildRunRequest
    approval_request: dict[str, Any] | None = None


async def _clear_child_processing_failure(
    *,
    parent_session_id: str,
    child_run_id: str,
) -> None:
    async with _CHILD_PROCESS_FAILURES_LOCK:
        _CHILD_PROCESS_FAILURES.pop((parent_session_id, child_run_id), None)


async def _record_child_processing_failure(
    *,
    parent_session_id: str,
    child_run_id: str,
    error: str,
) -> None:
    async with _CHILD_PROCESS_FAILURES_LOCK:
        _CHILD_PROCESS_FAILURES[(parent_session_id, child_run_id)] = error


async def _consume_child_processing_failure(
    *,
    parent_session_id: str,
    child_run_id: str,
) -> str | None:
    async with _CHILD_PROCESS_FAILURES_LOCK:
        return _CHILD_PROCESS_FAILURES.pop((parent_session_id, child_run_id), None)


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def open_session(session_factory: Any | None):
    if session_factory is None:
        return await create_session()
    return await maybe_await(session_factory())


async def close_session(session: Any) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result


def get_configurable(config: RunnableConfig | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    configurable = config.get("configurable")
    return configurable if isinstance(configurable, dict) else {}


def ensure_primary(state: dict[str, Any]) -> None:
    if state.get("active_agent") != "primary":
        raise ToolExecutionError("this orchestration tool may only be called by primary")


def build_subagent_identity_payload(row: AgentChildRun) -> dict[str, Any]:
    agent_number = get_child_run_agent_number(row.metadata_json)
    payload: dict[str, Any] = {"agent_key": row.agent_key}
    metadata: dict[str, Any] = {}
    if agent_number:
        payload["agent_number"] = agent_number
        metadata["agent_number"] = agent_number
    if metadata:
        payload["metadata"] = metadata
    return payload


def make_subagent_runner(
    *,
    state: dict[str, Any],
    configurable: dict[str, Any],
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    runner_factory = configurable.get("subagent_runner_factory") or SubagentRunner
    return runner_factory(
        session_factory=configurable.get("session_factory"),
        model_config=dict(state.get("model_config") or {}),
        project_id=str(state.get("project_id") or ""),
    )


async def persist_child_user_message(
    *,
    session_factory: Any | None,
    child_thread_id: str,
    task_id: str,
    project_id: str,
    content: str,
) -> None:
    session = await open_session(session_factory)
    try:
        message = await message_repo.insert_message(
            session,
            session_id=child_thread_id,
            task_id=task_id,
            project_id=project_id,
            role="user",
            status="sent",
            content=content,
            agent_id="primary",
            message_type="user_request",
        )
    finally:
        await close_session(session)

    payload = {
        "session_id": child_thread_id,
        "message_id": message.id,
        "correlation_id": message.id,
        "created_at": message.created_at.isoformat(),
        "updated_at": message.updated_at.isoformat(),
        "type": "text",
        "role": "user",
        "status": "completed",
        "display": "list",
        "content": message.content,
        "payload": {"kind": "user_request"},
    }
    buffer = get_agent_event_replay_buffer()
    async with buffer.session_lock(child_thread_id):
        buffer.record_unlocked("agent:text", payload)
        await emit(
            "agent:text",
            payload,
            room=agent_subagent_session_room(child_thread_id),
        )


async def resolve_child_run(
    *,
    parent_session_id: str,
    session_factory: Any | None,
    child_run_id: str | None = None,
    dispatch_id: str | None = None,
) -> AgentChildRun:
    session = await open_session(session_factory)
    try:
        row = await get_child_run_for_parent(
            session,
            parent_session_id=parent_session_id,
            child_run_id=child_run_id,
            dispatch_id=dispatch_id,
        )
        if row is None:
            raise ToolExecutionError("subagent thread not found")
        return row
    finally:
        await close_session(session)


async def ensure_child_processing(
    *,
    parent_session_id: str,
    child_run_id: str,
    runner: Any,
    resume_payload: dict[str, Any] | None = None,
) -> bool:
    registry = get_agent_run_registry()
    if await registry.is_child_running(parent_session_id, child_run_id):
        return False
    await _clear_child_processing_failure(
        parent_session_id=parent_session_id,
        child_run_id=child_run_id,
    )

    async def _run() -> None:
        try:
            if resume_payload is None:
                await runner.run(child_run_id)
            else:
                await runner.resume(child_run_id, resume_payload)
        except Exception as exc:
            error_text = str(exc) or type(exc).__name__
            await _record_child_processing_failure(
                parent_session_id=parent_session_id,
                child_run_id=child_run_id,
                error=error_text,
            )
            on_error = getattr(runner, "on_child_processing_error", None)
            if callable(on_error):
                await maybe_await(
                    on_error(
                        parent_session_id=parent_session_id,
                        child_run_id=child_run_id,
                        error=error_text,
                    )
                )
            logger.bind(
                parent_session_id=parent_session_id,
                child_run_id=child_run_id,
            ).opt(exception=True).error("Child processing crashed")
        finally:
            await registry.unregister_child(parent_session_id, child_run_id)
            on_finished = getattr(runner, "on_child_processing_finished", None)
            if callable(on_finished):
                await maybe_await(
                    on_finished(
                        parent_session_id=parent_session_id,
                        child_run_id=child_run_id,
                    )
                )

    task = asyncio.create_task(_run())
    registered = await registry.try_register_child(parent_session_id, child_run_id, task)
    if registered:
        return True
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    return False


async def wait_for_request_resolution(
    *,
    session_factory: Any | None,
    child_run_id: str,
    request_id: str,
) -> ChildRequestResolution:
    while True:
        session = await open_session(session_factory)
        try:
            child_run = await session.get(AgentChildRun, child_run_id)
            request = await session.get(AgentChildRunRequest, request_id)
            if child_run is None:
                raise ToolExecutionError(f"subagent thread not found: {child_run_id}")
            if request is None:
                raise ToolExecutionError(f"subagent request not found: {request_id}")

            if request.status == "completed":
                return ChildRequestResolution(child_run=child_run, request=request)
            if request.status == "cancelled":
                raise ToolExecutionError(request.error or "subagent request was cancelled")
            if request.status == "error":
                raise ToolExecutionError(request.error or "subagent request failed")
            if not child_run.is_active:
                raise ToolExecutionError("subagent thread is inactive")
            child_processing_error = await _consume_child_processing_failure(
                parent_session_id=child_run.parent_session_id,
                child_run_id=child_run_id,
            )
            if child_processing_error:
                raise ToolExecutionError(
                    f"subagent processing failed: {child_processing_error}"
                )
        finally:
            await close_session(session)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
