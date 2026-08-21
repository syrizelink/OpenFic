import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Literal, cast

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import ContextBuildError, build_context_parts
from app.agent_runtime.context.compaction.service import CompactionError, compact_window
from app.agent_runtime.context.compaction.window import (
    CompactionNoWindowError,
    select_compaction_window,
)
from app.agent_runtime.context.helpers import (
    compile_canonical_mentions,
    extract_referenced_skill_ids,
)
from app.audit import AuditContext
from app.agent_runtime.graph.orchestrator.graph import build_orchestrator_graph
from app.agent_runtime.graph.react_agent import _to_history_dict
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.model_config import without_api_key
from app.agent_runtime.persistence import (
    MessagePersister,
    PersistenceError,
    compaction_repo,
    load_history,
    repo,
)
from app.agent_runtime.persistence.model import AgentRunMessage
from app.agent_runtime.revisions import begin_user_revision, finalize_revision_status
from app.agent_runtime.runner.checkpointer import get_checkpointer, prune_thread_checkpoints
from app.agent_runtime.runner.event_translator import EventTranslator
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.agent_runtime.types import DEFAULT_AGENT_RECURSION_LIMIT
from app.agent_runtime.usage_cost import (
    calculate_llm_call_cost,
    extract_cache_read_tokens,
    extract_cache_write_tokens,
)
from app.core.ids import generate_id
from app.socket import emit
from app.socket.handlers import agent_session_room
from app.storage.database import _get_session_factory, create_session
from app.storage.repos import revision_repo
from app.storage.services import task_service

_HELD_EVENT_SESSION_IDS: ContextVar[frozenset[str]] = ContextVar(
    "session_runner_held_event_session_ids",
    default=frozenset(),
)


def _format_utc_iso_datetime(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        source = value if value.tzinfo else value.replace(tzinfo=UTC)
        return source.astimezone(UTC).isoformat()
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        source = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return source.astimezone(UTC).isoformat()
    return datetime.now(UTC).isoformat()


def _interrupt_payloads(state: object) -> list[dict[str, Any]]:
    tasks = getattr(state, "tasks", None) or []
    payloads: list[dict[str, Any]] = []
    for task_index, task in enumerate(tasks):
        interrupts = getattr(task, "interrupts", None) or []
        for interrupt_index, interrupt_obj in enumerate(interrupts):
            value = getattr(interrupt_obj, "value", None)
            if not isinstance(value, dict):
                continue
            payload = dict(value)
            interrupt_id = getattr(interrupt_obj, "id", None)
            if isinstance(interrupt_id, str) and interrupt_id:
                payload["interrupt_id"] = interrupt_id
                payload_type = payload.get("type")
                if payload_type == "tool_approval":
                    payload["approval_id"] = interrupt_id
                    payload["id"] = interrupt_id
                elif payload_type == "ask_user":
                    payload["action_id"] = interrupt_id
                    payload["id"] = interrupt_id
            payload["_interrupt_order"] = (
                payload.get("tool_index")
                if isinstance(payload.get("tool_index"), int)
                else task_index * 100 + interrupt_index
            )
            payloads.append(payload)
    ordered_payloads = sorted(
        payloads,
        key=lambda payload: int(payload.get("_interrupt_order") or 0),
    )
    for payload in ordered_payloads:
        payload.pop("_interrupt_order", None)
    return ordered_payloads


def _interrupt_resume_id(payload: dict[str, Any]) -> str | None:
    action_type = payload.get("action_type")
    key = "approval_id" if action_type == "tool_approval" else "action_id"
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


class SessionRunner:
    def __init__(
        self,
        session_id: str,
        task_id: str,
        model_config: dict,
        project_id: str = "",
        agent_key: str = "build",
    ):
        self._validate_model_config(model_config)
        self.session_id = session_id
        self.task_id = task_id
        self.model_config = dict(model_config)
        self.project_id = project_id
        self.agent_key = agent_key
        self._graph: CompiledStateGraph | None = None
        self._inject_queue: asyncio.Queue[tuple[str | None, str, str]] = asyncio.Queue()
        self._queued_user_messages: dict[str, tuple[str, datetime]] = {}
        self._queued_user_message_attachments: dict[str, list[dict[str, Any]]] = {}
        self._injected_user_message_attachments: dict[str, list[dict[str, Any]]] = {}
        self._cancelled_user_message_ids: set[str] = set()
        self._cancel_event = asyncio.Event()
        self._translator = EventTranslator(session_id)
        self._persister: MessagePersister | None = None

    @property
    def _room(self) -> str:
        return agent_session_room(self.session_id)

    @staticmethod
    def _validate_model_config(model_config: dict) -> None:
        val = model_config.get("max_context_tokens") if model_config else None
        if not isinstance(val, int) or val < 0:
            raise ContextBuildError(
                "config",
                "model_config.max_context_tokens must be a non-negative int",
            )

    def update_model_config(self, model_config: dict) -> None:
        self._validate_model_config(model_config)
        self.model_config = dict(model_config)

    async def _get_graph(self) -> CompiledStateGraph:
        if self._graph is None:
            checkpointer = await get_checkpointer()
            self._graph = build_orchestrator_graph(checkpointer=checkpointer)
        return self._graph

    async def _persist_user_message(
        self,
        content: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        message_id: str | None = None,
        created_at: datetime | None = None,
    ):
        session = await create_session()
        try:
            message = await repo.insert_message(
                session,
                session_id=self.session_id,
                task_id=self.task_id,
                project_id=self.project_id,
                role="user",
                status="sent",
                content=content,
                metadata={"attachments": attachments} if attachments else None,
                message_id=message_id,
                created_at=created_at,
            )
            return message
        finally:
            await session.close()

    async def _emit_user_message(
        self,
        content: str,
        revision_id: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
    ) -> None:
        data = {
            "session_id": self.session_id,
            "created_at": created_at or datetime.now(UTC).isoformat(),
            "type": "text",
            "role": "user",
            "status": "completed",
            "display": "list",
            "content": content,
            "payload": {
                "kind": "user_request",
                "revision_id": revision_id,
                **({"attachments": attachments} if attachments else {}),
            },
            "revision_id": revision_id,
            "is_checkpoint": True,
        }
        await emit("agent:text", data, room=self._room)

    async def _emit_pending_user_message(
        self,
        content: str,
        *,
        message_id: str,
        action: Literal["queued", "consumed", "cancelled"],
        attachments: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
    ) -> None:
        data = {
            "session_id": self.session_id,
            "message_id": message_id,
            "created_at": created_at or datetime.now(UTC).isoformat(),
            "content": content,
            "action": action,
            "payload": {
                "kind": "user_request",
                "message_id": message_id,
                "content": content,
                "action": action,
                "created_at": created_at or datetime.now(UTC).isoformat(),
                **({"attachments": attachments} if attachments else {}),
            },
        }
        await self._emit_agent_event("agent:pending_message", data)

    @asynccontextmanager
    async def _event_session_lock(self) -> AsyncIterator[None]:
        held_ids = _HELD_EVENT_SESSION_IDS.get()
        if self.session_id in held_ids:
            yield
            return

        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(self.session_id):
            token = _HELD_EVENT_SESSION_IDS.set(held_ids | {self.session_id})
            try:
                yield
            finally:
                _HELD_EVENT_SESSION_IDS.reset(token)

    async def _emit_agent_event(self, name: str, payload: dict) -> None:
        buffer = get_agent_event_replay_buffer()
        async with self._event_session_lock():
            if name != "agent:retry":
                buffer.clear_event_unlocked(self.session_id, "agent:retry")
            buffer.record_unlocked(name, payload)
            await emit(name, payload, room=self._room)

    async def _emit_tool_result(self, payload: dict[str, Any]) -> None:
        payload = {"session_id": self.session_id, **payload}
        if self._persister is not None:
            await self._persister.apply_tool_result(payload)
        await self._emit_agent_event("agent:tool_result", payload)

    async def _emit_retry_event(self, payload: dict[str, Any]) -> None:
        retry_payload = dict(payload)
        retry_payload["session_id"] = self.session_id
        await self._emit_agent_event("agent:retry", retry_payload)

    async def _clear_replay_run(self, run_id: object) -> None:
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(self.session_id):
            buffer.clear_run_unlocked(self.session_id, run_id)

    async def _clear_replay_session(self) -> None:
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(self.session_id):
            buffer.clear_session_unlocked(self.session_id)

    @staticmethod
    def _exception_reason(exc: Exception) -> str:
        reason = str(exc).strip()
        return reason or exc.__class__.__name__

    async def _handle_stream_failure(
        self,
        *,
        revision_id: str | None,
        error_type: Literal["persistence_failure", "runtime_failure"],
        exc: Exception,
    ) -> None:
        if self._persister is not None:
            try:
                await self._persister.finalize(reason="error")
            except PersistenceError:
                pass
        await emit(
            "agent:error",
            {
                "session_id": self.session_id,
                "type": error_type,
                "reason": self._exception_reason(exc),
            },
            room=self._room,
        )
        status_session = await create_session()
        try:
            await finalize_revision_status(status_session, revision_id, "failed")
            await status_session.commit()
        finally:
            await status_session.close()
        await self._clear_replay_session()

    async def _emit_pending_interrupts(self, state: object) -> None:
        interrupt_payloads = _interrupt_payloads(state)
        batch_id = generate_id()
        batch_total = len(interrupt_payloads)
        for batch_index, interrupt_payload in enumerate(interrupt_payloads):
            interrupt_payload["batch_id"] = batch_id
            interrupt_payload["batch_index"] = batch_index
            interrupt_payload["batch_total"] = batch_total
        for interrupt_payload in interrupt_payloads:
            preview_items = interrupt_payload.get("tool_result_previews")
            previewed_tool_call_ids: set[str] = set()
            if isinstance(preview_items, list):
                for preview_item in preview_items:
                    if not isinstance(preview_item, dict):
                        continue
                    tool_call_id = preview_item.get("tool_call_id")
                    tool_name = preview_item.get("tool_name")
                    preview = preview_item.get("preview")
                    if (
                        isinstance(tool_call_id, str)
                        and tool_call_id
                        and isinstance(tool_name, str)
                        and tool_name
                        and isinstance(preview, dict)
                    ):
                        previewed_tool_call_ids.add(tool_call_id)
                        await self._emit_agent_event(
                            "agent:tool_result",
                            {
                                "session_id": self.session_id,
                                "tool_call_id": tool_call_id,
                                "tool": tool_name,
                                "input": preview_item.get("args") or {},
                                "output": preview,
                                "is_preview": True,
                                "is_interrupt_preview": True,
                            },
                        )
            if self._persister is not None:
                await self._persister.apply_interrupt_preview(interrupt_payload)

            tool_call_id = interrupt_payload.get("tool_call_id")
            tool_name = interrupt_payload.get("tool_name")
            tool_result_preview = interrupt_payload.get("tool_result_preview")
            if (
                isinstance(tool_call_id, str)
                and tool_call_id
                and isinstance(tool_name, str)
                and tool_name
                and isinstance(tool_result_preview, dict)
                and tool_call_id not in previewed_tool_call_ids
            ):
                await self._emit_agent_event(
                    "agent:tool_result",
                    {
                        "session_id": self.session_id,
                        "tool_call_id": tool_call_id,
                        "tool": tool_name,
                        "input": interrupt_payload.get("args") or {},
                        "output": tool_result_preview,
                        "is_preview": True,
                        "is_interrupt_preview": True,
                    },
                )

        for interrupt_payload in interrupt_payloads:
            await emit(
                "agent:interrupt",
                {
                    "session_id": self.session_id,
                    **interrupt_payload,
                },
                room=self._room,
            )

    async def _current_root_checkpoint_id(self, graph: CompiledStateGraph) -> str | None:
        state = await graph.aget_state({"configurable": {"thread_id": self.session_id}})
        config = getattr(state, "config", None)
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        checkpoint_id = configurable.get("checkpoint_id")
        return checkpoint_id if isinstance(checkpoint_id, str) and checkpoint_id else None

    async def materialize_state(self, values: dict) -> str | None:
        graph = await self._get_graph()
        config = await graph.aupdate_state(
            {"configurable": {"thread_id": self.session_id}},
            values,
        )
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        checkpoint_id = configurable.get("checkpoint_id")
        return checkpoint_id if isinstance(checkpoint_id, str) and checkpoint_id else None

    def _normalize_usage_event(self, event_data: dict) -> dict:
        usage = event_data.get("usage") if isinstance(event_data, dict) else None
        usage_dict = usage if isinstance(usage, dict) else {}
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
        token_cache = extract_cache_read_tokens(usage_dict)
        if token_cache == 0:
            token_cache = max(int(usage_dict.get("token_cache") or 0), 0)
        token_cache_write = extract_cache_write_tokens(usage_dict)
        if token_cache_write == 0:
            token_cache_write = max(int(usage_dict.get("token_cache_write") or 0), 0)
        call_cost = calculate_llm_call_cost(
            token_input=token_input,
            token_output=token_output,
            token_cache=token_cache,
            token_cache_write=token_cache_write,
            input_price=float(self.model_config.get("input_price") or 0),
            output_price=float(self.model_config.get("output_price") or 0),
            cache_read_price=float(self.model_config.get("cache_read_price") or 0),
            cache_write_price=float(self.model_config.get("cache_write_price") or 0),
        )
        return {
            "session_id": self.session_id,
            "token_input": token_input,
            "token_output": token_output,
            "token_cache": token_cache,
            "cost": call_cost,
            "context_input_tokens": token_input,
            "context_length": int(self.model_config.get("max_context_tokens", 0)),
            **(
                {"usage_kind": event_data["usage_kind"]}
                if isinstance(event_data.get("usage_kind"), str)
                and event_data.get("usage_kind")
                else {}
            ),
        }

    async def _persist_task_usage_and_build_payload(
        self,
        event_data: dict,
    ) -> tuple[dict, dict]:
        normalized = self._normalize_usage_event(event_data)
        session = await create_session()
        try:
            task = await task_service.add_task_token_usage(
                session,
                task_id=self.task_id,
                token_input=int(normalized["token_input"]),
                token_output=int(normalized["token_output"]),
                token_cache=int(normalized["token_cache"]),
                cost=float(normalized["cost"]),
            )
            await session.commit()
        finally:
            await session.close()

        usage_payload = {
            "session_id": self.session_id,
            "token_input": int(task.token_input),
            "token_output": int(task.token_output),
            "token_cache": int(task.token_cache),
            "cost": float(task.cost),
            "context_input_tokens": int(task.context_input_tokens),
            "context_length": int(normalized["context_length"]),
        }
        delta_payload = {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "token_input": int(normalized["token_input"]),
            "token_output": int(normalized["token_output"]),
            "token_cache": int(normalized["token_cache"]),
            "cost": float(normalized["cost"]),
        }
        usage_kind = normalized.get("usage_kind")
        if isinstance(usage_kind, str) and usage_kind:
            usage_payload["usage_kind"] = usage_kind
            delta_payload["usage_kind"] = usage_kind
        return usage_payload, delta_payload

    async def _emit_persisted_task_usage_events(self, event_data: dict) -> None:
        async with self._event_session_lock():
            usage_payload, delta_payload = await self._persist_task_usage_and_build_payload(
                event_data
            )
            await self._emit_agent_event(
                "agent:task_usage_delta",
                delta_payload,
            )
            await self._emit_agent_event(
                "agent:usage",
                usage_payload,
            )

    async def _drain_inject_queue(
        self,
    ) -> list[tuple[str, str, str | None]]:
        """drain 全部排队消息；user 类型同步 mark_user_sent。返回 (role, content, msg_id) 列表。"""
        drained: list[tuple[str, str, str | None]] = []
        while not self._inject_queue.empty():
            msg_id, role, content = self._inject_queue.get_nowait()
            if role == "user" and msg_id is not None:
                consumed = await self._mark_injected_user_message_sent(msg_id)
                if not consumed:
                    continue
            drained.append((role, content, msg_id))
        return drained

    async def _prepare_run_persistence(self) -> list[BaseMessage]:
        """run 启动前：清 pending + load_history。返回 ReAct 初始 messages。"""
        session = await create_session()
        try:
            await repo.delete_pending_by_session(session, self.session_id)
            history_messages = await load_history(session, self.session_id)
        finally:
            await session.close()
        return history_messages

    def _build_runtime_config(
        self,
        *,
        runtime_session: AsyncSession,
        runtime_context: dict[str, Any],
        audit_context: AuditContext,
    ) -> RunnableConfig:
        async def _noop_node_event_sink(_payload: dict[str, Any]) -> None:
            return None

        node_event_sink = (
            self._persister.persist_node_event
            if self._persister is not None
            else _noop_node_event_sink
        )
        return {
            "recursion_limit": DEFAULT_AGENT_RECURSION_LIMIT,
            "max_concurrency": 10,
            "configurable": {
                "thread_id": self.session_id,
                "db_session": runtime_session,
                "runtime_context": runtime_context,
                "audit_context": audit_context,
                "node_event_sink": node_event_sink,
                "retry_event_sink": self._emit_retry_event,
                "agent_event_sink": self._emit_agent_event,
                "tool_result_sink": self._emit_tool_result,
                "compaction_usage_sink": self._emit_persisted_task_usage_events,
                "inject_queue": self._inject_queue,
                "inject_message_consumed_sink": self._mark_injected_user_message_sent,
                "inject_message_attachments": self._get_injected_user_message_attachments,
                "model_config": self.model_config,
            }
        }

    async def _mark_injected_user_message_sent(self, message_id: str) -> bool:
        if not isinstance(message_id, str) or not message_id:
            return False
        if message_id in self._cancelled_user_message_ids:
            self._cancelled_user_message_ids.discard(message_id)
            return False
        queued = self._queued_user_messages.pop(message_id, None)
        if queued is not None:
            content, created_at = queued
            attachments = self._queued_user_message_attachments.pop(message_id, [])
            created_at_iso = _format_utc_iso_datetime(created_at)
            await self._emit_pending_user_message(
                content,
                attachments=attachments,
                message_id=message_id,
                action="consumed",
                created_at=created_at_iso,
            )
            await self._persist_user_message(
                content,
                message_id=message_id,
                attachments=attachments,
                created_at=created_at,
            )
            await self._emit_runtime_user_message(
                content,
                message_id=message_id,
                attachments=attachments,
                created_at=created_at_iso,
            )
            return True
        if self._persister is None:
            return False
        await self._persister.mark_user_sent(message_id)
        return True

    async def _emit_runtime_user_message(
        self,
        content: str,
        *,
        message_id: str,
        attachments: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
    ) -> None:
        data = {
            "session_id": self.session_id,
            "message_id": message_id,
            "created_at": created_at or datetime.now(UTC).isoformat(),
            "type": "text",
            "role": "user",
            "status": "completed",
            "display": "list",
            "content": content,
            "payload": {
                "kind": "user_request",
                **({"attachments": attachments} if attachments else {}),
            },
            "is_checkpoint": False,
        }
        await self._emit_agent_event("agent:text", data)

    async def _compile_user_message_content(
        self,
        content: str,
        *,
        db_session: AsyncSession | None = None,
    ) -> str:
        if not content or ("<of-mention" not in content and "<of-skill" not in content):
            return content
        if db_session is not None:
            return await compile_canonical_mentions(content, db_session)
        session = await create_session()
        try:
            return await compile_canonical_mentions(content, session)
        finally:
            await session.close()

    async def _begin_user_turn(
        self,
        *,
        graph: CompiledStateGraph,
        user_request: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> tuple[Any, Any]:
        pre_run_checkpoint_id = await self._current_root_checkpoint_id(graph)
        persistence_kwargs = {"attachments": attachments} if attachments else {}
        user_message = await self._persist_user_message(user_request, **persistence_kwargs)

        revision_session = await create_session()
        try:
            revision = await begin_user_revision(
                revision_session,
                project_id=self.project_id,
                task_id=self.task_id,
                agent_session_id=self.session_id,
                user_message_id=user_message.id,
                user_message_seq=user_message.seq,
                message=f"用户消息: {user_request}",
                pre_run_checkpoint_id=pre_run_checkpoint_id,
                graph_thread_id=self.session_id,
            )
            await revision_session.commit()
        finally:
            await revision_session.close()

        user_message_created_at = getattr(user_message, "created_at", None)
        emitted_created_at = _format_utc_iso_datetime(user_message_created_at)

        await self._emit_user_message(
            user_request,
            revision.id,
            attachments=attachments,
            created_at=emitted_created_at,
        )
        return user_message, revision

    async def _begin_existing_user_turn(
        self,
        *,
        graph: CompiledStateGraph,
        user_request: str,
        user_message_id: str,
    ) -> tuple[Any, Any]:
        pre_run_checkpoint_id = await self._current_root_checkpoint_id(graph)
        revision_session = await create_session()
        try:
            user_message = await revision_session.get(AgentRunMessage, user_message_id)
            if user_message is None:
                raise ValueError(f"user message not found: {user_message_id}")
            revision = await begin_user_revision(
                revision_session,
                project_id=self.project_id,
                task_id=self.task_id,
                agent_session_id=self.session_id,
                user_message_id=user_message.id,
                user_message_seq=user_message.seq,
                message=f"系统提醒: {user_request}",
                pre_run_checkpoint_id=pre_run_checkpoint_id,
                graph_thread_id=self.session_id,
            )
            await revision_session.commit()
        finally:
            await revision_session.close()

        return user_message, revision

    def _make_persister(self) -> MessagePersister:
        factory = _get_session_factory()

        def make_session():
            return factory()

        return MessagePersister(
            session_id=self.session_id,
            task_id=self.task_id,
            project_id=self.project_id,
            db_session_factory=make_session,
        )

    async def compact(self) -> dict[str, int | str]:
        session = await create_session()
        try:
            history_messages = await load_history(session, self.session_id)
            node_messages = [_to_history_dict(message) for message in history_messages]
            state = cast(AgentRuntimeState, {
                "session_id": self.session_id,
                "task_id": self.task_id,
                "project_id": self.project_id,
                "model_config": without_api_key(self.model_config),
                "active_agent": None,
                "agent_key": self.agent_key,
                "is_completed": False,
                "error": None,
                "retry_count": 0,
                "user_request": "",
                "user_attachments": [],
                "current_revision_id": None,
            })
            agent_name = state.get("active_agent") or state.get("agent_key") or "build"
            parts = await build_context_parts(
                state,
                agent_name,
                node_messages,
                session,
            )
            history = [
                part
                for part in parts
                if (part.metadata or {}).get("part") == "history"
            ]
            existing_compactions = await compaction_repo.list_by_session(
                session,
                self.session_id,
            )
            try:
                window = select_compaction_window(
                    history,
                    existing_compactions,
                    int(self.model_config["max_context_tokens"]),
                )
            except CompactionNoWindowError as exc:
                raise CompactionError(
                    "no_compactable_window",
                    "没有可压缩的上下文窗口",
                ) from exc

            result = await compact_window(
                session,
                state=state,
                window=window,
                trigger="manual",
                event_sink=self._emit_agent_event,
                usage_sink=self._emit_persisted_task_usage_events,
                model_config=self.model_config,
            )
            return {
                "compaction_id": result.id,
                "start_seq": result.start_seq,
                "end_seq": result.end_seq,
                "source_input_tokens": result.source_input_tokens,
                "summary_tokens": result.summary_tokens,
            }
        finally:
            await session.close()

    async def run(
        self,
        user_request: str,
        attachments: list[dict[str, Any]] | None = None,
        user_message_id: str | None = None,
    ) -> None:
        runtime_session = await create_session()
        runtime_context: dict[str, Any] = {}
        self._persister = self._make_persister()
        audit_context = AuditContext(
            session_id=self.session_id,
            task_id=self.task_id,
            project_id=self.project_id,
        )
        config = self._build_runtime_config(
            runtime_session=runtime_session,
            runtime_context=runtime_context,
            audit_context=audit_context,
        )
        self._cancel_event.clear()
        reason: Literal["done", "cancelled", "error"] = "done"
        revision = None
        try:
            history_messages = await self._prepare_run_persistence()
            graph = await self._get_graph()
            referenced_skill_ids = extract_referenced_skill_ids([user_request])
            if user_message_id is None:
                compiled_user_request = await self._compile_user_message_content(
                    user_request,
                    db_session=runtime_session,
                )
                _user_message, revision = await self._begin_user_turn(
                    graph=graph,
                    user_request=user_request,
                    attachments=attachments,
                )
                state_user_request = compiled_user_request
            else:
                _user_message, revision = await self._begin_existing_user_turn(
                    graph=graph,
                    user_request=user_request,
                    user_message_id=user_message_id,
                )
                state_user_request = ""

            audit_context.set_revision_id(revision.id)

            initial_state = {
                "session_id": self.session_id,
                "task_id": self.task_id,
                "project_id": self.project_id,
                "model_config": without_api_key(self.model_config),
                "active_agent": None,
                "agent_key": self.agent_key,
                "is_completed": False,
                "error": None,
                "retry_count": 0,
                "user_request": state_user_request,
                "user_attachments": attachments or [],
                "current_revision_id": revision.id,
                "referenced_skill_ids": list(referenced_skill_ids),
                "messages": history_messages,
            }
            async for event in graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                event_dict = cast(dict[str, Any], event)
                if self._cancel_event.is_set():
                    reason = "cancelled"
                    break

                ws_events = self._translator.translate(event_dict)
                if ws_events:
                    for ws_event in ws_events if isinstance(ws_events, list) else [ws_events]:
                        payload = ws_event["data"]
                        if ws_event["name"] == "agent:usage":
                            await self._emit_persisted_task_usage_events(payload)
                            continue
                        await self._emit_agent_event(ws_event["name"], payload)
                await self._persister.handle(event_dict)
                if event_dict.get("event") in {"on_chat_model_end", "on_tool_end"}:
                    await self._clear_replay_run(event_dict.get("run_id"))

            if user_message_id is not None:
                await self._persister.mark_user_sent(user_message_id)

            await self._persister.finalize(reason=reason)
            if reason == "cancelled":
                status_session = await create_session()
                try:
                    await finalize_revision_status(status_session, revision.id, "cancelled")
                    await status_session.commit()
                finally:
                    await status_session.close()
                await self._clear_replay_session()
                return
        except asyncio.CancelledError:
            try:
                await self._persister.finalize(reason="cancelled")
            except PersistenceError:
                pass
            status_session = await create_session()
            try:
                await finalize_revision_status(
                    status_session,
                    revision.id if revision is not None else None,
                    "cancelled",
                )
                await status_session.commit()
            finally:
                await status_session.close()
            await self._clear_replay_session()
            return
        except PersistenceError as e:
            await self._handle_stream_failure(
                revision_id=revision.id if revision is not None else None,
                error_type="persistence_failure",
                exc=e,
            )
            raise
        except Exception as e:
            await self._handle_stream_failure(
                revision_id=revision.id if revision is not None else None,
                error_type="runtime_failure",
                exc=e,
            )
            raise
        finally:
            await runtime_session.close()
            await self._prune_thread_checkpoints()

        # Check for interrupt after stream ends
        state = await graph.aget_state(
            {"configurable": {"thread_id": self.session_id}}
        )
        if state.next:
            status_session = await create_session()
            try:
                finalized = await finalize_revision_status(
                    status_session, revision.id, "interrupted"
                )
                await status_session.commit()
            finally:
                await status_session.close()
            if not finalized:
                await self._clear_replay_session()
                return
            await self._emit_pending_interrupts(state)
            await self._clear_replay_session()
        else:
            status_session = await create_session()
            try:
                finalized = await finalize_revision_status(
                    status_session, revision.id, "completed"
                )
                await status_session.commit()
            finally:
                await status_session.close()
            if not finalized:
                await self._clear_replay_session()
                return
            await emit(
                "agent:done",
                {
                    "session_id": self.session_id,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                room=self._room,
            )
            await self._clear_replay_session()

    async def _prune_thread_checkpoints(self) -> None:
        try:
            session = await create_session()
            try:
                checkpointer = await get_checkpointer()
                deleted_rows = await prune_thread_checkpoints(
                    session,
                    checkpointer,
                    self.session_id,
                )
                if deleted_rows:
                    logger.info(
                        f"Pruned {deleted_rows} checkpoint rows for session {self.session_id}"
                    )
            finally:
                await session.close()
        except Exception:
            logger.exception(
                f"Failed to prune checkpoints for session {self.session_id}"
            )

    async def inject_message(
        self,
        content: str,
        message_id: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        self._injected_user_message_attachments[message_id] = attachments or []
        await self._inject_queue.put((message_id, "user", content))

    def _get_injected_user_message_attachments(self, message_id: str) -> list[dict[str, Any]]:
        return list(self._injected_user_message_attachments.get(message_id, []))

    async def queue_pending_user_message(
        self,
        content: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        message_id = generate_id()
        created_at = datetime.now(UTC)
        self._queued_user_messages[message_id] = (content, created_at)
        self._queued_user_message_attachments[message_id] = attachments or []
        created_at_iso = _format_utc_iso_datetime(created_at)
        await self._emit_pending_user_message(
            content,
            message_id=message_id,
            action="queued",
            attachments=attachments,
            created_at=created_at_iso,
        )
        await self.inject_message(content, message_id, attachments)
        return {
            "message_id": message_id,
            "content": content,
            "created_at": created_at_iso,
        }

    async def cancel_pending_user_message(self, message_id: str) -> dict[str, str] | None:
        queued = self._queued_user_messages.pop(message_id, None)
        if queued is None:
            return None
        self._cancelled_user_message_ids.add(message_id)
        content, created_at = queued
        attachments = self._queued_user_message_attachments.pop(message_id, [])
        created_at_iso = _format_utc_iso_datetime(created_at)
        await self._emit_pending_user_message(
            content,
            message_id=message_id,
            action="cancelled",
            attachments=attachments,
            created_at=created_at_iso,
        )
        return {
            "message_id": message_id,
            "content": content,
            "created_at": created_at_iso,
        }

    def peek_next_pending_user_message(self) -> tuple[str, str] | None:
        for message_id, (content, _created_at) in self._queued_user_messages.items():
            if message_id in self._cancelled_user_message_ids:
                continue
            return message_id, content
        return None

    async def consume_next_pending_user_message_for_continuation(
        self,
    ) -> tuple[str, str] | None:
        pending: tuple[str, str, datetime] | None = None
        for message_id, (content, created_at) in self._queued_user_messages.items():
            if message_id in self._cancelled_user_message_ids:
                continue
            pending = (message_id, content, created_at)
            break
        if pending is None:
            return None

        message_id, content, created_at = pending
        attachments = self._queued_user_message_attachments.get(message_id, [])
        created_at_iso = _format_utc_iso_datetime(created_at)
        if attachments:
            await self._persist_user_message(
                content,
                attachments=attachments,
                message_id=message_id,
                created_at=created_at,
            )
        else:
            await self._persist_user_message(
                content,
                message_id=message_id,
                created_at=created_at,
            )

        self._queued_user_messages.pop(message_id, None)
        next_queue: asyncio.Queue[tuple[str | None, str, str]] = asyncio.Queue()
        while not self._inject_queue.empty():
            queued_message_id, role, queued_content = self._inject_queue.get_nowait()
            if queued_message_id == message_id:
                continue
            await next_queue.put((queued_message_id, role, queued_content))
        self._inject_queue = next_queue

        pending_event_kwargs = {"attachments": attachments} if attachments else {}
        await self._emit_pending_user_message(
            content,
            message_id=message_id,
            action="consumed",
            created_at=created_at_iso,
            **pending_event_kwargs,
        )
        runtime_event_kwargs = {"attachments": attachments} if attachments else {}
        await self._emit_runtime_user_message(
            content,
            message_id=message_id,
            created_at=created_at_iso,
            **runtime_event_kwargs,
        )
        return message_id, content

    async def cancel_and_continue(self, new_message: str, message_id: str) -> None:
        self._cancel_event.set()
        await self._inject_queue.put((None, "system", "[系统] 上一条回复被用户中止"))
        await self._inject_queue.put((message_id, "user", new_message))

    def cancel(self) -> None:
        self._cancel_event.set()
        self._queued_user_messages.clear()
        self._queued_user_message_attachments.clear()
        self._injected_user_message_attachments.clear()
        self._cancelled_user_message_ids.clear()
        self._inject_queue = asyncio.Queue()

    async def resume_interrupt_batch(
        self, batch_id: str, responses: list[dict[str, Any]]
    ) -> None:
        await self.resume(
            {
                "action_type": "interrupt_batch",
                "batch_id": batch_id,
                "responses": responses,
            }
        )

    async def resume(self, payload: dict) -> None:
        graph = await self._get_graph()
        runtime_session = await create_session()
        snapshot = await graph.aget_state(
            {"configurable": {"thread_id": self.session_id}}
        )
        values = snapshot.values if isinstance(getattr(snapshot, "values", None), dict) else {}
        revision_id = values.get("current_revision_id")
        revision_id = revision_id if isinstance(revision_id, str) and revision_id else None
        runtime_context: dict[str, Any] = {}
        audit_context = AuditContext(
            session_id=self.session_id,
            task_id=self.task_id,
            project_id=self.project_id,
        )
        if revision_id:
            audit_context.set_revision_id(revision_id)
        if self._persister is None:
            self._persister = self._make_persister()
        config = self._build_runtime_config(
            runtime_session=runtime_session,
            runtime_context=runtime_context,
            audit_context=audit_context,
        )
        self._cancel_event.clear()
        # The cancel endpoint commits this status before it signals in-memory
        # runners. Together with the registry guard, this stops a queued resume
        # task from clearing the cancellation signal and reviving the checkpoint.
        if await get_agent_run_registry().is_cancelled(self.session_id):
            await runtime_session.close()
            return
        if revision_id:
            revision = await revision_repo.get_by_id(runtime_session, revision_id)
            if revision is not None and revision.status == "cancelled":
                await runtime_session.close()
                return

        reason: Literal["done", "cancelled", "error"] = "done"
        try:
            resume_value: dict[str, Any] | dict[str, dict[str, Any]] = payload
            is_terminal_skip_resume = payload.get("skipped") is True
            if payload.get("action_type") == "interrupt_batch":
                state = await graph.aget_state(
                    {"configurable": {"thread_id": self.session_id}}
                )
                pending = _interrupt_payloads(state)
                pending_by_id = {
                    item["interrupt_id"]: item
                    for item in pending
                    if isinstance(item.get("interrupt_id"), str)
                }
                responses = payload.get("responses")
                if not isinstance(responses, list) or not responses:
                    raise ValueError("并行中断响应不能为空")
                if any(
                    not isinstance(response, dict)
                    or response.get("interrupt_id") not in pending_by_id
                    for response in responses
                ):
                    raise ValueError("存在无效或已处理的并行中断响应")
                if set(response["interrupt_id"] for response in responses) != set(
                    pending_by_id
                ):
                    raise ValueError("必须一次提交本批全部并行中断响应")
                is_terminal_skip_resume = any(
                    isinstance(response, dict)
                    and response.get("action_type") == "clarification"
                    and response.get("skipped") is True
                    for response in responses
                )
                resume_value = {
                    response["interrupt_id"]: response for response in responses
                }
            elif payload.get("action_type") == "tool_approval":
                state = await graph.aget_state(
                    {"configurable": {"thread_id": self.session_id}}
                )
                interrupt_payloads = _interrupt_payloads(state)
                resume_id = _interrupt_resume_id(payload)
                matching = next(
                    (
                        item
                        for item in interrupt_payloads
                        if item.get("approval_id") == resume_id
                    ),
                    None,
                )
                if matching is None or not resume_id:
                    raise ValueError("待恢复的工具审批不存在或已处理")
                resume_value = {resume_id: payload}
            elif payload.get("action_type") == "clarification":
                state = await graph.aget_state(
                    {"configurable": {"thread_id": self.session_id}}
                )
                interrupt_payloads = _interrupt_payloads(state)
                resume_id = _interrupt_resume_id(payload)
                matching = next(
                    (
                        item
                        for item in interrupt_payloads
                        if item.get("action_id") == resume_id
                    ),
                    None,
                )
                if matching is None or not resume_id:
                    raise ValueError("待恢复的问题不存在或已处理")
                resume_value = {resume_id: payload}
            stream_options = (
                {"durability": "exit"} if is_terminal_skip_resume else {}
            )
            async for event in graph.astream_events(
                Command(resume=resume_value),
                config=config,
                version="v2",
                **stream_options,
            ):
                event_dict = cast(dict[str, Any], event)
                if self._cancel_event.is_set():
                    reason = "cancelled"
                    break
                ws_events = self._translator.translate(event_dict)
                if ws_events:
                    for ws_event in ws_events if isinstance(ws_events, list) else [ws_events]:
                        payload = ws_event["data"]
                        if ws_event["name"] == "agent:usage":
                            await self._emit_persisted_task_usage_events(payload)
                            continue
                        await self._emit_agent_event(ws_event["name"], payload)
                await self._persister.handle(event_dict)
                if event_dict.get("event") in {"on_chat_model_end", "on_tool_end"}:
                    await self._clear_replay_run(event_dict.get("run_id"))
            await self._persister.finalize(reason=reason)
            if reason == "cancelled":
                status_session = await create_session()
                try:
                    await finalize_revision_status(status_session, revision_id, "cancelled")
                    await status_session.commit()
                finally:
                    await status_session.close()
                await self._clear_replay_session()
                return
        except asyncio.CancelledError:
            try:
                await self._persister.finalize(reason="cancelled")
            except PersistenceError:
                pass
            status_session = await create_session()
            try:
                await finalize_revision_status(status_session, revision_id, "cancelled")
                await status_session.commit()
            finally:
                await status_session.close()
            await self._clear_replay_session()
            return
        except PersistenceError as e:
            await self._handle_stream_failure(
                revision_id=revision_id,
                error_type="persistence_failure",
                exc=e,
            )
            raise
        except Exception as e:
            await self._handle_stream_failure(
                revision_id=revision_id,
                error_type="runtime_failure",
                exc=e,
            )
            raise
        finally:
            await runtime_session.close()

        state = await graph.aget_state(
            {"configurable": {"thread_id": self.session_id}}
        )
        if state.next:
            status_session = await create_session()
            try:
                finalized = await finalize_revision_status(
                    status_session, revision_id, "interrupted"
                )
                await status_session.commit()
            finally:
                await status_session.close()
            if not finalized:
                await self._clear_replay_session()
                return
            await self._emit_pending_interrupts(state)
            await self._clear_replay_session()
        else:
            status_session = await create_session()
            try:
                finalized = await finalize_revision_status(
                    status_session, revision_id, "completed"
                )
                await status_session.commit()
            finally:
                await status_session.close()
            if not finalized:
                await self._clear_replay_session()
                return
            await emit(
                "agent:done",
                {
                    "session_id": self.session_id,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                room=self._room,
            )
            await self._clear_replay_session()

    async def start_new_run(self, user_request: str) -> None:
        self._graph = None

        await self.run(user_request)
