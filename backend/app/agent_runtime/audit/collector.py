"""Collect and persist agent runtime audit data."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from loguru import logger

from app.agent_runtime.audit.queue import enqueue_audit_log, next_call_sequence
from app.core.ids import generate_id
from app.storage.models.agent_audit_log import AgentAuditLog


def _pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _nested_usage_int(usage: dict[str, Any], path: tuple[str, str]) -> int:
    parent = usage.get(path[0])
    if not isinstance(parent, dict):
        return 0
    return _to_int(parent.get(path[1]))


def _usage_int(
    usage: dict[str, Any],
    *keys: str,
    path: tuple[str, str] | None = None,
    fallback_path: tuple[str, str] | None = None,
) -> int:
    for key in keys:
        value = _to_int(usage.get(key))
        if value:
            return value
    if path:
        value = _nested_usage_int(usage, path)
        if value:
            return value
    if fallback_path:
        return _nested_usage_int(usage, fallback_path)
    return 0


def normalize_usage_tokens(usage: dict[str, Any] | None) -> dict[str, int]:
    """Normalize provider usage payloads into OpenFic token counters."""
    if not usage:
        return {
            "token_input": 0,
            "token_output": 0,
            "tokens_total": 0,
            "token_cache": 0,
        }

    token_input = _usage_int(usage, "input_tokens", "prompt_tokens")
    token_output = _usage_int(usage, "output_tokens", "completion_tokens")
    tokens_total = _usage_int(usage, "total_tokens") or token_input + token_output
    token_cache = _usage_int(
        usage,
        "cached_tokens",
        "cache_read_input_tokens",
        path=("input_token_details", "cache_read"),
        fallback_path=("prompt_tokens_details", "cached_tokens"),
    )
    return {
        "token_input": token_input,
        "token_output": token_output,
        "tokens_total": tokens_total,
        "token_cache": token_cache,
    }


@dataclass
class ToolCallRecord:
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: dict[str, Any] | None = None
    success: bool = False
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMCallRecord:
    id: str
    task_id: str | None
    session_id: str | None
    parent_session_id: str | None
    child_run_id: str | None
    project_id: str
    revision_id: str | None
    agent_node: str
    call_sequence: int
    model_id: str
    model_provider: str | None
    model_name: str | None
    request_messages: list[dict[str, Any]] = field(default_factory=list)
    response_content: str = ""
    response_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_records: list[ToolCallRecord] = field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    token_cache: int = 0
    latency_ms: int = 0
    first_token_ms: int | None = None
    start_time: float = 0.0
    status: str = "pending"
    error_type: str | None = None
    error_message: str | None = None
    error_status_code: int | None = None
    tool_calls_count: int = 0
    tool_calls_success_count: int = 0
    tool_calls_failed_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMCallAudit:
    """Context manager for one audited LLM invocation."""

    def __init__(
        self,
        collector: "AuditCollector",
        agent_node: str,
        model_id: str,
        model_provider: str | None = None,
        model_name: str | None = None,
        request_messages: list[BaseMessage] | list[dict[str, Any]] | None = None,
    ) -> None:
        self.collector = collector
        self.agent_node = agent_node
        self.model_id = model_id
        self.model_provider = model_provider
        self.model_name = model_name
        self.request_messages = request_messages
        self.record: LLMCallRecord | None = None
        self._finished = False

    async def __aenter__(self) -> "LLMCallAudit":
        sequence = await next_call_sequence(self.collector.session_id)
        record_id = generate_id()

        self.record = LLMCallRecord(
            id=record_id,
            task_id=self.collector.task_id,
            session_id=self.collector.session_id,
            parent_session_id=self.collector.parent_session_id,
            child_run_id=self.collector.child_run_id,
            project_id=self.collector.project_id,
            revision_id=self.collector.revision_id,
            agent_node=self.agent_node,
            call_sequence=sequence,
            model_id=self.model_id,
            model_provider=self.model_provider,
            model_name=self.model_name,
            request_messages=self._serialize_messages(self.request_messages),
            start_time=time.time(),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc is not None:
            self.record_error(
                error_type=exc_type.__name__ if exc_type else type(exc).__name__,
                error_message=str(exc),
            )
        await self.finish(status="error" if exc is not None else "success")
        return False

    @staticmethod
    def _message_role(message: BaseMessage) -> str:
        if isinstance(message, SystemMessage):
            return "system"
        if isinstance(message, HumanMessage):
            return "user"
        if isinstance(message, AIMessage):
            return "assistant"
        if isinstance(message, ToolMessage):
            return "tool"
        return getattr(message, "type", "unknown")

    @staticmethod
    def _serialize_messages(
        request_messages: list[BaseMessage] | list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        messages_data: list[dict[str, Any]] = []
        if not request_messages:
            return messages_data

        for msg in request_messages:
            if isinstance(msg, BaseMessage):
                payload: dict[str, Any] = {
                    "type": msg.__class__.__name__,
                    "content": msg.content,
                    "role": LLMCallAudit._message_role(msg),
                }
                if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                    payload["tool_calls"] = msg.tool_calls
                if isinstance(msg, ToolMessage):
                    payload["tool_call_id"] = msg.tool_call_id
                messages_data.append(payload)
            elif isinstance(msg, dict):
                messages_data.append(msg)
        return messages_data

    def record_response(
        self,
        content: str = "",
        tool_calls: list[dict[str, Any]] | None = None,
        usage: dict[str, Any] | None = None,
        first_token_ms: int | None = None,
    ) -> None:
        if not self.record:
            logger.warning("no active audit record")
            return

        self.record.response_content = content
        self.record.response_tool_calls = tool_calls or []
        self.record.first_token_ms = first_token_ms

        if usage:
            normalized_usage = normalize_usage_tokens(usage)
            self.record.tokens_input = normalized_usage["token_input"]
            self.record.tokens_output = normalized_usage["token_output"]
            self.record.tokens_total = normalized_usage["tokens_total"]
            self.record.token_cache = normalized_usage["token_cache"]

    def record_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: dict[str, Any] | None = None,
        success: bool = True,
        latency_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.record:
            logger.warning("no active audit record")
            return

        self.record.tool_call_records.append(
            ToolCallRecord(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                success=success,
                latency_ms=latency_ms,
                metadata=metadata or {},
            )
        )

        self.record.tool_calls_count += 1
        if success:
            self.record.tool_calls_success_count += 1
        else:
            self.record.tool_calls_failed_count += 1

    def record_error(
        self,
        error_type: str | None = None,
        error_message: str | None = None,
        error_status_code: int | None = None,
    ) -> None:
        if not self.record:
            logger.warning("no active audit record")
            return

        self.record.status = "error"
        self.record.error_type = error_type
        self.record.error_message = error_message
        self.record.error_status_code = error_status_code

    async def finish(self, status: str = "success") -> AgentAuditLog | None:
        if self._finished:
            return None
        self._finished = True

        if not self.record:
            logger.warning("no active audit record")
            return None

        record = self.record
        if record.status != "error":
            record.status = status
        record.latency_ms = int((time.time() - record.start_time) * 1000)

        tool_call_results = [
            {
                "tool_name": tc.tool_name,
                "tool_args": tc.tool_args,
                "result": tc.tool_result,
                "success": tc.success,
                "latency_ms": tc.latency_ms,
                "metadata": tc.metadata,
            }
            for tc in record.tool_call_records
        ]

        audit_log = AgentAuditLog(
            id=record.id,
            task_id=record.task_id,
            session_id=record.session_id,
            parent_session_id=record.parent_session_id,
            child_run_id=record.child_run_id,
            project_id=record.project_id,
            revision_id=record.revision_id,
            agent_node=record.agent_node,
            call_sequence=record.call_sequence,
            model_id=record.model_id,
            model_provider=record.model_provider,
            model_name=record.model_name,
            request_messages=_pretty_json(record.request_messages)
            if record.request_messages
            else None,
            response_content=record.response_content or None,
            response_tool_calls=_pretty_json(record.response_tool_calls)
            if record.response_tool_calls
            else None,
            tool_call_results=_pretty_json(tool_call_results)
            if tool_call_results
            else None,
            tokens_input=record.tokens_input,
            tokens_output=record.tokens_output,
            tokens_total=record.tokens_total,
            token_cache=record.token_cache,
            latency_ms=record.latency_ms,
            first_token_ms=record.first_token_ms,
            status=record.status,
            error_type=record.error_type,
            error_message=record.error_message,
            error_status_code=record.error_status_code,
            tool_calls_count=record.tool_calls_count,
            tool_calls_success_count=record.tool_calls_success_count,
            tool_calls_failed_count=record.tool_calls_failed_count,
            extra_data=_pretty_json(record.metadata) if record.metadata else None,
        )

        await enqueue_audit_log(audit_log)
        self.collector._records.append(audit_log)
        return audit_log


class AuditCollector:
    """Collects audit records for one agent runtime session."""

    def __init__(
        self,
        db_session: Any | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
        parent_session_id: str | None = None,
        child_run_id: str | None = None,
        project_id: str = "",
        revision_id: str | None = None,
    ):
        self.db_session = db_session
        self.session_id = session_id
        self.task_id = task_id
        self.parent_session_id = parent_session_id
        self.child_run_id = child_run_id
        self.project_id = project_id
        self.revision_id = revision_id
        self._records: list[AgentAuditLog] = []

    def llm_call(
        self,
        agent_node: str,
        model_id: str,
        model_provider: str | None = None,
        model_name: str | None = None,
        request_messages: list[BaseMessage] | list[dict[str, Any]] | None = None,
    ) -> LLMCallAudit:
        return LLMCallAudit(
            collector=self,
            agent_node=agent_node,
            model_id=model_id,
            model_provider=model_provider,
            model_name=model_name,
            request_messages=request_messages,
        )

    def set_revision_id(self, revision_id: str) -> None:
        self.revision_id = revision_id

    def set_task_id(self, task_id: str) -> None:
        self.task_id = task_id

    def set_session_id(self, session_id: str) -> None:
        self.session_id = session_id

    def get_records(self) -> list[AgentAuditLog]:
        return self._records.copy()

    @property
    def total_tokens(self) -> int:
        return sum(record.tokens_total for record in self._records)

    @property
    def total_latency_ms(self) -> int:
        return sum(record.latency_ms or 0 for record in self._records)
