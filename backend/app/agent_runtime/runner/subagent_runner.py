from __future__ import annotations

import inspect
import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import Command

from app.agent_runtime.agents.definitions import (
    AgentDefinition,
    load_agent_definition,
)
from app.agent_runtime.audit.collector import AuditCollector
from app.agent_runtime.agents.tool_categories import get_tool_names_for_categories
from app.agent_runtime.graph.react_agent import create_react_agent
from app.agent_runtime.persistence import MessagePersister
from app.agent_runtime.persistence.child_runs import (
    claim_next_child_run_request,
    complete_child_run_request,
    count_pending_child_run_requests,
    get_child_run_agent_number,
    get_running_child_run_request,
    record_child_run_pending_approval,
    update_child_run_status,
)
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence.model import AgentChildRun, AgentChildRunRequest
from app.agent_runtime.runner.checkpointer import get_checkpointer
from app.agent_runtime.runner.event_translator import EventTranslator
from app.agent_runtime.runner.event_scope import SUBAGENT_CHILD_EVENT_TAG
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.agent_runtime.tools import ToolRegistry
from app.agent_runtime.tools.hooks import auth_hook, chapter_refresh_post_hook, note_refresh_post_hook, world_entry_refresh_post_hook
from app.agent_runtime.tools.impls.skill.skill import skill_tool_names_for_definition
from app.agent_runtime.types import (
    DEFAULT_AGENT_RECURSION_LIMIT,
    ReactAgentConfig,
    TerminationCondition,
)
from app.core.encryption import EncryptionService
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.repos import model_provider_repo, model_repo
from app.socket import emit
from app.socket.handlers import (
    agent_session_room,
    agent_subagent_session_room,
    agent_subagents_room,
    background_project_room,
)
from app.settings import settings
from app.storage.database import _get_session_factory, create_session
from app.storage.repos import setting_repo
from app.storage.services import task_service


SYSTEM_DEFAULT_MODEL_REFERENCE = "__system_default_model__"
SYSTEM_LIGHT_MODEL_REFERENCE = "__system_light_model__"


def build_child_messages(history: list[BaseMessage], *, content: str) -> list[BaseMessage]:
    return [*history, HumanMessage(content=content)]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _open_session(session_factory: Any | None):
    if session_factory is None:
        return await create_session()
    return await _maybe_await(session_factory())


async def _close_session(session: Any) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result


async def _read_setting_model_id(session: Any, key: str) -> str | None:
    setting = await setting_repo.get_by_key(session, key)
    value = setting.value.strip() if setting and setting.value else ""
    return value or None


async def _resolve_model_record_id(
    session: Any,
    *,
    configured_model_id: str | None,
) -> str | None:
    """Resolve a configured model reference to a model record nanoid.

    ``configured_model_id`` and the ``default_model``/``light_model`` settings all
    store the model record's primary key (nanoid), not the provider API model
    name. This returns the nanoid of the model record the subagent should use,
    or ``None`` when nothing is configured (caller falls back to the inherited
    parent model config).
    """
    if configured_model_id == SYSTEM_LIGHT_MODEL_REFERENCE:
        return (
            await _read_setting_model_id(session, "light_model")
            or await _read_setting_model_id(session, "default_model")
        )

    if configured_model_id in (None, "", SYSTEM_DEFAULT_MODEL_REFERENCE):
        return await _read_setting_model_id(session, "default_model")

    return configured_model_id


async def _build_model_config_from_record(session: Any, record_id: str) -> dict[str, Any] | None:
    """Resolve a model record nanoid to a full model config dict.

    Mirrors the parent agent and background-job resolution: load the model +
    provider, decrypt the API key, and return the complete config used by
    ``create_chat_model``. Returns ``None`` when the record or provider is
    missing.
    """
    model = await model_repo.get_by_id(session, record_id)
    if model is None:
        return None

    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        return None

    api_key = EncryptionService(settings.encryption_key).decrypt(provider.api_key_encrypted)
    return {
        "provider_type": provider.provider_type,
        "base_url": provider.url,
        "api_key": api_key,
        "model_id": model.model_id,
        "max_context_tokens": model.context_length,
        "temperature": model.temperature,
        "top_p": model.top_p,
        "top_k": model.top_k,
        "max_tokens": model.max_tokens,
        "frequency_penalty": model.frequency_penalty,
        "presence_penalty": model.presence_penalty,
        "deepseek_reasoning_effort": model.deepseek_reasoning_effort,
        "deepseek_thinking_type": model.deepseek_thinking_type,
    }


async def _resolve_agent_model_config(
    session: Any,
    *,
    configured_model_id: str | None,
    inherited_config: dict[str, Any],
) -> dict[str, Any]:
    """Resolve the model config a subagent should use.

    When the subagent (or the configured default/light setting) points at a
    model record, the provider, base_url, api_key and real ``model_id`` are
    resolved from that record. When nothing is configured, the inherited
    parent model config is returned unchanged.
    """
    record_id = await _resolve_model_record_id(
        session,
        configured_model_id=configured_model_id,
    )
    if record_id:
        resolved = await _build_model_config_from_record(session, record_id)
        if resolved is not None:
            return resolved
    return dict(inherited_config)


def _extract_interrupts(result_state: dict[str, Any]) -> list[Any]:
    interrupts = result_state.get("__interrupt__")
    if isinstance(interrupts, tuple):
        return list(interrupts)
    if isinstance(interrupts, list):
        return list(interrupts)
    return []


def _interrupt_value(interrupt_obj: Any) -> dict[str, Any]:
    value = getattr(interrupt_obj, "value", None)
    return dict(value) if isinstance(value, dict) else {}


def _interrupt_id(interrupt_obj: Any, value: dict[str, Any]) -> str:
    raw_id = (
        value.get("approval_id")
        or value.get("id")
        or getattr(interrupt_obj, "id", None)
    )
    if isinstance(raw_id, str) and raw_id:
        return raw_id
    return "child-approval"


def _last_assistant_content(messages: list[BaseMessage]) -> str | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and isinstance(message.content, str):
            content = message.content.strip()
            if content:
                return content
    return None


def _subagent_status_value(row: AgentChildRun, *, pending_count: int) -> str:
    if row.pending_approval_id or row.status == "waiting_user":
        return "waiting_user"
    if row.status == "running":
        return "running"
    if row.status == "queued" or pending_count > 0:
        return "queued"
    return row.status


def _should_publish_parent_subagent_status(
    row: AgentChildRun,
    *,
    request_kind: str | None = None,
) -> bool:
    return True


class SubagentRunner:
    def __init__(
        self,
        *,
        session_factory: Any | None = None,
        model_config: dict[str, Any],
        project_id: str,
    ) -> None:
        self.session_factory = session_factory
        self.model_config = model_config
        self.project_id = project_id

    async def _load_child_run(self, child_run_id: str) -> AgentChildRun:
        session = await _open_session(self.session_factory)
        try:
            row = await session.get(AgentChildRun, child_run_id)
            if row is None:
                raise ValueError(f"child run not found: {child_run_id}")
            return row
        finally:
            await _close_session(session)

    async def _load_history(self, child_thread_id: str) -> list[BaseMessage]:
        session = await _open_session(self.session_factory)
        try:
            return await load_history(session, child_thread_id)
        finally:
            await _close_session(session)

    async def _load_agent_definition(self, agent_key: str) -> AgentDefinition:
        session = await _open_session(self.session_factory)
        try:
            return await load_agent_definition(session, agent_key)
        finally:
            await _close_session(session)

    async def _build_tools(
        self,
        definition: AgentDefinition,
        runtime_state: dict[str, Any],
    ):
        if not definition.enabled or definition.kind != "subagent":
            raise ValueError(f"agent is not an enabled subagent: {definition.key}")
        names = list(get_tool_names_for_categories(definition.enabled_tool_categories))
        session = await _open_session(self.session_factory)
        try:
            names.extend(await skill_tool_names_for_definition(definition, session))
        finally:
            await _close_session(session)
        return ToolRegistry.get_tools(
            names=names,
            state=runtime_state,
            pre_hooks=[auth_hook],
            post_hooks=[chapter_refresh_post_hook, note_refresh_post_hook, world_entry_refresh_post_hook],
        )

    async def _build_runtime_state(
        self,
        row: AgentChildRun,
        content: str,
        *,
        parent_revision_id: str | None = None,
    ) -> dict[str, Any]:
        session = await _open_session(self.session_factory)
        try:
            task = await task_service.get_task(session, row.parent_task_id)
            current_revision_id = parent_revision_id or task.current_revision_id
        finally:
            await _close_session(session)

        return {
            "session_id": row.child_thread_id,
            "task_id": row.parent_task_id,
            "project_id": self.project_id,
            "model_config": self.model_config,
            "active_agent": row.agent_key,
            "is_completed": False,
            "error": None,
            "retry_count": 0,
            "user_request": content,
            "current_revision_id": current_revision_id,
            "parent_session_id": row.parent_session_id,
            "parent_thread_id": row.parent_thread_id,
            "child_run_id": row.id,
            "dispatch_id": row.dispatch_id,
        }

    async def _build_graph(
        self,
        row: AgentChildRun,
        definition: AgentDefinition,
        runtime_state: dict[str, Any],
    ):
        agent_config = ReactAgentConfig(
            name=row.agent_key,
            tools=await self._build_tools(definition, runtime_state),
            termination=TerminationCondition(mode="no_tool_call"),
        )
        model_config = dict(self.model_config)
        session = await _open_session(self.session_factory)
        try:
            model_config = await _resolve_agent_model_config(
                session,
                configured_model_id=definition.model_id,
                inherited_config=model_config,
            )
        finally:
            await _close_session(session)
        model = create_chat_model(ModelConfig(**model_config))
        return create_react_agent(
            agent_config,
            model=model,
            checkpointer=await get_checkpointer(),
        )

    async def _invoke_graph(
        self,
        row: AgentChildRun,
        graph: Any,
        graph_input: Any,
        runtime_state: dict[str, Any],
        audit_collector: AuditCollector,
    ) -> dict[str, Any]:
        translator = EventTranslator(
            row.child_thread_id,
            allow_subagent_child_events=True,
        )
        persister = self._make_child_persister(row)
        runtime_session = await _open_session(self.session_factory)
        final_state: dict[str, Any] | None = None

        async def agent_event_sink(name: str, payload: dict[str, Any]) -> None:
            child_payload = dict(payload)
            child_payload.setdefault("session_id", row.child_thread_id)
            await self._emit_child_agent_event(
                row.child_thread_id,
                name,
                child_payload,
            )

        async def compaction_usage_sink(payload: dict[str, Any]) -> None:
            normalized = self._normalize_usage_event(row.child_thread_id, payload)
            normalized["parent_session_id"] = row.parent_session_id
            await self._persist_parent_task_usage_and_emit_delta(row, normalized)

        try:
            async for event in graph.astream_events(
                graph_input,
                config={
                    "recursion_limit": DEFAULT_AGENT_RECURSION_LIMIT,
                    "tags": [SUBAGENT_CHILD_EVENT_TAG],
                    "configurable": {
                        "thread_id": row.child_thread_id,
                        "db_session": runtime_session,
                        "runtime_state": runtime_state,
                        "audit_collector": audit_collector,
                        "agent_event_sink": agent_event_sink,
                        "compaction_usage_sink": compaction_usage_sink,
                    },
                },
                version="v2",
            ):
                ws_events = translator.translate(event)
                if ws_events:
                    for ws_event in (
                        ws_events if isinstance(ws_events, list) else [ws_events]
                    ):
                        payload = ws_event["data"]
                        if ws_event["name"] == "agent:usage":
                            payload = self._normalize_usage_event(
                                row.child_thread_id,
                                payload,
                            )
                            await self._persist_parent_task_usage_and_emit_delta(
                                row,
                                payload,
                            )
                        await self._emit_child_agent_event(
                            row.child_thread_id,
                            ws_event["name"],
                            payload,
                        )
                await persister.handle(event)
                if event.get("event") in {"on_chat_model_end", "on_tool_end", "on_tool_error"}:
                    await self._clear_child_replay_run(
                        row.child_thread_id,
                        event.get("run_id"),
                    )
                if event.get("event") == "on_chain_end":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, dict):
                        final_state = output
            await persister.finalize(reason="done")
            snapshot_state = await self._load_child_graph_state(graph, row.child_thread_id)
            if snapshot_state is not None:
                final_state = snapshot_state
            if final_state is None:
                raise ValueError("subagent stream completed without final state")
            return final_state
        except asyncio.CancelledError:
            try:
                await persister.finalize(reason="cancelled")
            finally:
                await self._clear_child_replay_session(row.child_thread_id)
            raise
        except Exception:
            try:
                await persister.finalize(reason="error")
            finally:
                await self._clear_child_replay_session(row.child_thread_id)
            raise
        finally:
            await _close_session(runtime_session)

    def _make_child_persister(self, row: AgentChildRun) -> MessagePersister:
        factory = self.session_factory or _get_session_factory()
        return MessagePersister(
            session_id=row.child_thread_id,
            task_id=row.parent_task_id,
            project_id=self.project_id,
            db_session_factory=factory,
            allow_subagent_child_events=True,
        )

    async def _load_child_graph_state(
        self,
        graph: Any,
        child_thread_id: str,
    ) -> dict[str, Any] | None:
        aget_state = getattr(graph, "aget_state", None)
        if not callable(aget_state):
            return None

        state = await aget_state({"configurable": {"thread_id": child_thread_id}})
        values = state.values if isinstance(getattr(state, "values", None), dict) else {}
        if not isinstance(values, dict) or not values:
            return None

        result = dict(values)
        if getattr(state, "next", None):
            tasks = getattr(state, "tasks", None) or []
            if tasks and hasattr(tasks[0], "interrupts") and tasks[0].interrupts:
                result["__interrupt__"] = list(tasks[0].interrupts)
        return result

    async def _emit_child_agent_event(
        self,
        session_id: str,
        name: str,
        payload: dict[str, Any],
    ) -> None:
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(session_id):
            buffer.record_unlocked(name, payload)
            await emit(name, payload, room=agent_subagent_session_room(session_id))

    async def _emit_child_interrupt(
        self,
        row: AgentChildRun,
        approval_request: dict[str, Any],
    ) -> None:
        await self._emit_child_agent_event(
            row.child_thread_id,
            "agent:interrupt",
            {
                "session_id": row.child_thread_id,
                **approval_request,
            },
        )

    async def _clear_child_replay_run(self, session_id: str, run_id: object) -> None:
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(session_id):
            buffer.clear_run_unlocked(session_id, run_id)

    async def _clear_child_replay_session(self, session_id: str) -> None:
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(session_id):
            buffer.clear_session_unlocked(session_id)

    async def _emit_child_terminal_event(
        self,
        row: AgentChildRun,
        *,
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        await emit(
            event_name,
            payload,
            room=agent_subagent_session_room(row.child_thread_id),
        )
        await self._clear_child_replay_session(row.child_thread_id)

    async def _publish_child_terminal_result(
        self,
        child_run_id: str,
        result: dict[str, Any],
    ) -> None:
        row = await self._load_child_run(child_run_id)
        error = result.get("error")
        error_text = error if isinstance(error, str) and error else None
        if error_text or row.status == "error":
            await self._emit_child_terminal_event(
                row,
                event_name="agent:error",
                payload={
                    "session_id": row.child_thread_id,
                    "type": "subagent_failed",
                    "reason": error_text or row.error or "Subagent run failed",
                },
            )
            return
        if result.get("approval_request") or row.status != "completed":
            return
        await self._emit_child_terminal_event(
            row,
            event_name="agent:done",
            payload={
                "session_id": row.child_thread_id,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

    def _normalize_usage_event(self, session_id: str, event_data: dict[str, Any]) -> dict[str, Any]:
        usage = event_data.get("usage") if isinstance(event_data, dict) else None
        usage_dict = usage if isinstance(usage, dict) else {}
        input_details = usage_dict.get("input_token_details")
        input_details_dict = input_details if isinstance(input_details, dict) else {}
        token_input = int(
            usage_dict.get("input_tokens")
            or usage_dict.get("prompt_tokens")
            or usage_dict.get("token_input")
            or 0
        )
        token_output = int(
            usage_dict.get("output_tokens")
            or usage_dict.get("completion_tokens")
            or usage_dict.get("token_output")
            or 0
        )
        token_cache = int(
            usage_dict.get("cache_read_tokens")
            or input_details_dict.get("cache_read")
            or input_details_dict.get("cached_tokens")
            or usage_dict.get("token_cache")
            or 0
        )
        return {
            "session_id": session_id,
            "token_input": token_input,
            "token_output": token_output,
            "token_cache": token_cache,
            "context_input_tokens": token_input,
            "context_length": int(self.model_config.get("max_context_tokens", 0)),
            **(
                {"usage_kind": event_data["usage_kind"]}
                if isinstance(event_data.get("usage_kind"), str)
                and event_data.get("usage_kind")
                else {}
            ),
        }

    async def _persist_parent_task_usage_and_emit_delta(
        self,
        row: AgentChildRun,
        payload: dict[str, Any],
    ) -> None:
        token_input = int(payload.get("token_input", 0))
        token_output = int(payload.get("token_output", 0))
        token_cache = int(payload.get("token_cache", 0))
        context_input_tokens = int(payload.get("context_input_tokens", 0))
        context_length = int(payload.get("context_length", 0))
        delta_payload = {
            "session_id": row.parent_session_id,
            "task_id": row.parent_task_id,
            "token_input": token_input,
            "token_output": token_output,
            "token_cache": token_cache,
        }
        usage_snapshot = {
            "token_input": token_input,
            "token_output": token_output,
            "token_cache": token_cache,
            "context_input_tokens": context_input_tokens,
            "context_length": context_length,
        }

        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(row.parent_session_id):
            session = await _open_session(self.session_factory)
            try:
                await task_service.add_task_token_usage(
                    session,
                    task_id=row.parent_task_id,
                    token_input=token_input,
                    token_output=token_output,
                    token_cache=token_cache,
                )
                child_row = await session.get(AgentChildRun, row.id)
                if child_row is None:
                    raise ValueError(f"child run not found: {row.id}")
                metadata = dict(child_row.metadata_json or {})
                metadata["token_usage"] = usage_snapshot
                child_row.metadata_json = metadata
                child_row.updated_at = datetime.now(UTC)
                session.add(child_row)
                await session.commit()
            finally:
                await _close_session(session)

            await emit(
                "agent:task_usage_delta",
                delta_payload,
                room=agent_session_room(row.parent_session_id),
            )

    async def _build_subagent_status_payload(self, row: AgentChildRun) -> dict[str, Any]:
        pending_count = await self._count_pending_requests(row.id)
        payload = {
            "parent_session_id": row.parent_session_id,
            "child_run_id": row.id,
            "child_thread_id": row.child_thread_id,
            "agent_key": row.agent_key,
            "status": _subagent_status_value(row, pending_count=pending_count),
            "queued_messages": pending_count,
            "is_active": row.is_active,
            "pending_approval": (
                dict(row.pending_approval_json)
                if row.pending_approval_json is not None
                else None
            ),
        }
        agent_number = get_child_run_agent_number(row.metadata_json)
        if agent_number:
            payload["agent_number"] = agent_number
        return payload

    async def _emit_parent_subagent_status(
        self,
        row: AgentChildRun,
        payload: dict[str, Any],
    ) -> None:
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(row.parent_session_id):
            buffer.record_unlocked("agent:subagent_status", payload)
            await emit(
                "agent:subagent_status",
                payload,
                room=agent_subagents_room(row.parent_session_id),
            )

    async def _publish_parent_subagent_status_row(
        self,
        row: AgentChildRun,
        *,
        request_kind: str | None = None,
        force: bool = False,
    ) -> None:
        if not force and not _should_publish_parent_subagent_status(
            row,
            request_kind=request_kind,
        ):
            return
        payload = await self._build_subagent_status_payload(row)
        await self._emit_parent_subagent_status(row, payload)

    async def publish_parent_subagent_status(self, child_run_id: str) -> None:
        row = await self._load_child_run(child_run_id)
        await self._publish_parent_subagent_status_row(row, force=True)

    async def _count_pending_requests(self, child_run_id: str) -> int:
        session = await _open_session(self.session_factory)
        try:
            return await count_pending_child_run_requests(session, child_run_id)
        finally:
            await _close_session(session)

    async def _set_parent_task_running_state(
        self,
        *,
        parent_task_id: str,
        parent_session_id: str,
        is_running: bool,
    ) -> None:
        session = await _open_session(self.session_factory)
        try:
            task = await task_service.update_task(
                session,
                task_id=parent_task_id,
                is_running=is_running,
            )
            await session.commit()
        finally:
            await _close_session(session)

        if self.project_id:
            await emit(
                "background:event",
                {
                    "type": "task_run_status_updated",
                    "job_type": "agent_runtime",
                    "subject_type": "project",
                    "subject_id": self.project_id,
                    "project_id": self.project_id,
                    "task_id": parent_task_id,
                    "agent_session_id": parent_session_id,
                    "is_running": is_running,
                    "payload": {"is_running": is_running},
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                    "project_revision": time.time_ns(),
                },
                room=background_project_room(self.project_id),
            )

    async def _mark_child_running(self, child_run_id: str) -> AgentChildRun:
        session = await _open_session(self.session_factory)
        try:
            row = await update_child_run_status(
                session,
                child_run_id,
                "running",
            )
            if row.pending_approval_id or row.pending_approval_json is not None:
                row.pending_approval_id = None
                row.pending_approval_json = None
                row.updated_at = datetime.now(UTC)
                session.add(row)
                await session.commit()
                await session.refresh(row)
            return row
        finally:
            await _close_session(session)

    async def _record_pending_approval(
        self,
        row: AgentChildRun,
        interrupt_obj: Any,
        *,
        request_kind: str,
    ) -> dict[str, Any]:
        value = _interrupt_value(interrupt_obj)
        approval_id = _interrupt_id(interrupt_obj, value)
        if approval_id == "child-approval":
            approval_id = f"{row.id}:approval"
        approval_request = {
            **value,
            "approval_id": approval_id,
            "id": approval_id,
            "child_run_id": row.id,
            "child_thread_id": row.child_thread_id,
            "parent_session_id": row.parent_session_id,
            "parent_thread_id": row.parent_thread_id,
            "agent_key": row.agent_key,
            "dispatch_id": row.dispatch_id,
        }
        session = await _open_session(self.session_factory)
        try:
            updated_row = await record_child_run_pending_approval(
                session,
                row.id,
                approval_id=approval_id,
                approval_request=approval_request,
            )
        finally:
            await _close_session(session)
        await self._publish_parent_subagent_status_row(
            updated_row,
            request_kind=request_kind,
        )
        return {"approval_request": approval_request}

    async def _complete_request(
        self,
        row: AgentChildRun,
        request_row: AgentChildRunRequest,
        *,
        assistant_content: str | None = None,
        error: str | None = None,
    ) -> AgentChildRun:
        session = await _open_session(self.session_factory)
        try:
            if error is None:
                await complete_child_run_request(
                    session,
                    request_row.id,
                    assistant_content=assistant_content,
                )
            else:
                await complete_child_run_request(
                    session,
                    request_row.id,
                    status="error",
                    assistant_content=assistant_content,
                    error=error,
                )
            refreshed = await session.get(AgentChildRun, row.id)
            if refreshed is None:
                raise ValueError(f"child run not found: {row.id}")
            if error is not None:
                refreshed.error = error
                await session.commit()
                await session.refresh(refreshed)
            return refreshed
        finally:
            await _close_session(session)

    async def _run_request(
        self,
        row: AgentChildRun,
        request_row: AgentChildRunRequest,
        *,
        resume_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if resume_payload is not None:
            row = await self._mark_child_running(row.id)
            await self._publish_parent_subagent_status_row(
                row,
                request_kind=request_row.request_kind,
            )

        definition = await self._load_agent_definition(row.agent_key)
        history = await self._load_history(row.child_thread_id)
        runtime_state = await self._build_runtime_state(
            row,
            request_row.content,
            parent_revision_id=request_row.parent_revision_id,
        )
        graph = await self._build_graph(row, definition, runtime_state)
        graph_input: Any
        if resume_payload is None:
            graph_input = {
                "messages": build_child_messages(history, content=request_row.content),
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            }
        else:
            graph_input = Command(resume=resume_payload)
        audit_collector = AuditCollector(
            session_id=row.child_thread_id,
            task_id=row.parent_task_id,
            parent_session_id=row.parent_session_id,
            child_run_id=row.id,
            project_id=self.project_id,
        )

        try:
            result_state = await self._invoke_graph(
                row,
                graph,
                graph_input,
                runtime_state,
                audit_collector,
            )
        except Exception as exc:
            refreshed = await self._complete_request(
                row,
                request_row,
                error=str(exc),
            )
            await self._publish_parent_subagent_status_row(
                refreshed,
                request_kind=request_row.request_kind,
            )
            return {"error": str(exc)}

        interrupts = _extract_interrupts(result_state)
        if interrupts:
            pending_result = await self._record_pending_approval(
                row,
                interrupts[0],
                request_kind=request_row.request_kind,
            )
            approval_request = pending_result.get("approval_request")
            if isinstance(approval_request, dict) and approval_request:
                await self._emit_child_interrupt(row, approval_request)
            return pending_result

        assistant_content = _last_assistant_content(result_state.get("messages") or [])
        if assistant_content is None:
            error = "subagent turn completed without assistant content"
            refreshed = await self._complete_request(row, request_row, error=error)
            await self._publish_parent_subagent_status_row(
                refreshed,
                request_kind=request_row.request_kind,
            )
            return {"error": error}

        refreshed = await self._complete_request(
            row,
            request_row,
            assistant_content=assistant_content,
        )
        await self._publish_parent_subagent_status_row(
            refreshed,
            request_kind=request_row.request_kind,
        )
        return {
            "assistant_content": assistant_content,
            "request_id": request_row.id,
        }

    async def _claim_next_request(self, child_run_id: str) -> AgentChildRunRequest | None:
        session = await _open_session(self.session_factory)
        try:
            return await claim_next_child_run_request(session, child_run_id)
        finally:
            await _close_session(session)

    async def _load_running_request(self, child_run_id: str) -> AgentChildRunRequest | None:
        session = await _open_session(self.session_factory)
        try:
            return await get_running_child_run_request(
                session,
                child_run_id=child_run_id,
            )
        finally:
            await _close_session(session)

    async def _drive(
        self,
        child_run_id: str,
        *,
        resume_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_result: dict[str, Any] = {}
        last_request_kind: str | None = None
        next_resume_payload = resume_payload
        while True:
            row = await self._load_child_run(child_run_id)
            if not row.is_active:
                await self._publish_parent_subagent_status_row(
                    row,
                    request_kind=last_request_kind,
                )
                return last_result or {"cancelled": True}

            if next_resume_payload is not None:
                request_row = await self._load_running_request(child_run_id)
                if request_row is None:
                    return last_result
            else:
                request_row = await self._claim_next_request(child_run_id)
                if request_row is None:
                    await self._publish_parent_subagent_status_row(
                        row,
                        request_kind=last_request_kind,
                    )
                    return last_result
                row = await self._load_child_run(child_run_id)
                await self._publish_parent_subagent_status_row(
                    row,
                    request_kind=request_row.request_kind,
                )

            last_request_kind = request_row.request_kind
            last_result = await self._run_request(
                row,
                request_row,
                resume_payload=next_resume_payload,
            )
            if last_result.get("approval_request") or last_result.get("error"):
                return last_result
            next_resume_payload = None

    async def run(self, child_run_id: str) -> dict[str, Any]:
        result = await self._drive(child_run_id)
        await self._publish_child_terminal_result(child_run_id, result)
        return result

    async def resume(
        self,
        child_run_id: str,
        resume_payload: dict[str, Any],
    ) -> dict[str, Any]:
        result = await self._drive(child_run_id, resume_payload=resume_payload)
        await self._publish_child_terminal_result(child_run_id, result)
        return result

    async def on_child_processing_finished(
        self,
        *,
        parent_session_id: str,
        child_run_id: str,
    ) -> None:
        row = await self._load_child_run(child_run_id)
        pending_count = await self._count_pending_requests(child_run_id)
        if row.is_active and row.status == "queued" and pending_count > 0:
            from app.agent_runtime.tools.impls.orchestration.common import (
                ensure_child_processing,
            )

            await ensure_child_processing(
                parent_session_id=parent_session_id,
                child_run_id=child_run_id,
                runner=self,
            )
            return

        registry = get_agent_run_registry()
        if await registry.is_running(parent_session_id):
            return

        await self._set_parent_task_running_state(
            parent_task_id=row.parent_task_id,
            parent_session_id=parent_session_id,
            is_running=False,
        )

    async def on_child_processing_error(
        self,
        *,
        parent_session_id: str,
        child_run_id: str,
        error: str,
    ) -> None:
        session = await _open_session(self.session_factory)
        try:
            running_request = await get_running_child_run_request(
                session,
                child_run_id=child_run_id,
            )
            if running_request is not None:
                await complete_child_run_request(
                    session,
                    running_request.id,
                    status="error",
                    error=error,
                )
                row = await session.get(AgentChildRun, child_run_id)
            else:
                row = await update_child_run_status(
                    session,
                    child_run_id,
                    "error",
                    error=error,
                )
            if row is None:
                return
        finally:
            await _close_session(session)

        await self._publish_parent_subagent_status_row(row, force=True)
        await self._emit_child_terminal_event(
            row,
            event_name="agent:error",
            payload={
                "session_id": row.child_thread_id,
                "type": "subagent_failed",
                "reason": error,
            },
        )
