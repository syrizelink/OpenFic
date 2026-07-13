from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.compaction.window import CompactionWindow
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.model_config import to_client_model_config
from app.agent_runtime.persistence import compaction_repo
from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.compaction_types import (
    CompactionTrigger,
    PersistedCompaction,
)
from app.agent_runtime.persistence.errors import PersistenceWriteError
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.storage.services import prompt_chain_service


EventSink = Callable[[str, dict[str, Any]], Awaitable[None] | None]
UsageSink = Callable[[dict[str, Any]], Awaitable[None] | None]
PromptRole = Literal["system", "user", "assistant"]

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


class CompactionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


async def compact_window(
    db_session: AsyncSession,
    *,
    state: AgentRuntimeState | dict[str, Any],
    window: CompactionWindow,
    trigger: CompactionTrigger,
    event_sink: EventSink | None = None,
    usage_sink: UsageSink | None = None,
    model_config: Mapping[str, Any] | None = None,
) -> PersistedCompaction:
    session_id = str(state.get("session_id") or "")
    task_id = str(state.get("task_id") or "")
    project_id = str(state.get("project_id") or "")

    await _emit_event(
        event_sink,
        "agent:compaction_start",
        {
            "session_id": session_id,
            "task_id": task_id,
            "trigger": trigger,
            "start_seq": window.start_seq,
            "end_seq": window.end_seq,
            "source_input_tokens": window.source_input_tokens,
        },
    )

    try:
        messages = await _build_messages(db_session, window=window)
    except CompactionError as exc:
        await _emit_error(
            event_sink,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            error=exc,
        )
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Failed to build compaction prompt")
        error = CompactionError("prompt_error", "压缩提示词加载失败，当前请求已中止")
        await _emit_error(
            event_sink,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            error=error,
        )
        raise error from exc

    try:
        effective_model_config = (
            dict(model_config) if model_config is not None else _model_config(state)
        )
        model = create_chat_model(ModelConfig(**to_client_model_config(effective_model_config)))
        response = await model.ainvoke(messages)
    except Exception as exc:
        logger.opt(exception=True).error("Compaction LLM request failed")
        error = CompactionError("llm_error", "压缩失败，当前请求已中止")
        await _emit_error(
            event_sink,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            error=error,
        )
        raise error from exc

    try:
        summary = _summary_from_response(response)
    except CompactionError as exc:
        await _emit_error(
            event_sink,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            error=exc,
        )
        raise

    usage = _extract_usage(response)
    token_input, token_output, token_cache = _token_counts(usage)
    summary_tokens = max(token_output, 0)

    try:
        result = await compaction_repo.insert_compaction(
            db_session,
            session_id=session_id,
            task_id=task_id,
            project_id=project_id,
            start_seq=window.start_seq,
            end_seq=window.end_seq,
            summary=summary,
            trigger=trigger,
            source_input_tokens=window.source_input_tokens,
            summary_tokens=summary_tokens,
        )
    except PersistenceWriteError as exc:
        logger.opt(exception=True).error("Failed to persist compaction")
        code = (
            "compaction_conflict"
            if "compaction_conflict" in str(exc)
            else "compaction_persist_failed"
        )
        message = (
            "压缩范围已被写入，当前请求已中止"
            if code == "compaction_conflict"
            else "压缩结果写入失败，当前请求已中止"
        )
        error = CompactionError(code, message)
        await _emit_error(
            event_sink,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            error=error,
        )
        raise error from exc

    try:
        await _persist_display_marker(
            db_session,
            compaction=result,
            trigger=trigger,
        )
    except PersistenceWriteError as exc:
        logger.opt(exception=True).error("Failed to persist compaction display marker")
        error = CompactionError(
            "compaction_display_persist_failed",
            "压缩显示消息写入失败，当前请求已中止",
        )
        await _emit_error(
            event_sink,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            error=error,
        )
        raise error from exc

    await _emit_usage(
        usage_sink,
        _usage_payload(
            usage=usage,
            session_id=session_id,
            task_id=task_id,
            trigger=trigger,
            token_input=token_input,
            token_output=token_output,
            token_cache=token_cache,
        ),
    )
    await _emit_event(
        event_sink,
        "agent:compaction_success",
        {
            "session_id": session_id,
            "task_id": task_id,
            "compaction_id": result.id,
            "trigger": trigger,
            "start_seq": result.start_seq,
            "end_seq": result.end_seq,
            "source_input_tokens": result.source_input_tokens,
            "summary_tokens": result.summary_tokens,
        },
    )
    return result


async def _persist_display_marker(
    db_session: AsyncSession,
    *,
    compaction: PersistedCompaction,
    trigger: CompactionTrigger,
) -> None:
    await message_repo.insert_message(
        db_session,
        session_id=compaction.session_id,
        task_id=compaction.task_id,
        project_id=compaction.project_id,
        role="system",
        status="complete",
        content="已进行压缩",
        message_type="compaction",
        display_channel="list",
        llm_visibility="hidden",
        metadata={
            "kind": "compaction",
            "compaction_id": compaction.id,
            "trigger": trigger,
        },
        message_id=f"compaction:{compaction.id}",
        created_at=compaction.created_at,
    )


async def _build_messages(
    db_session: AsyncSession,
    *,
    window: CompactionWindow,
) -> list[BaseMessage]:
    version = await prompt_chain_service.get_latest_version_with_entries_or_default(
        db_session,
        prompt_id="session-compaction",
    )
    entries = sorted(
        (entry for entry in version.entries if entry.is_enabled),
        key=lambda entry: entry.order_index,
    )

    messages: list[BaseMessage] = []
    for entry in entries:
        content = entry.content
        if not content:
            continue
        role = entry.role
        if role not in {"system", "user", "assistant"}:
            raise CompactionError("prompt_error", "压缩提示词配置无效")
        messages.append(_to_langchain_message(cast(PromptRole, role), content))

    messages.append(HumanMessage(content=window.transcript))
    return messages


def _to_langchain_message(role: PromptRole, content: str) -> BaseMessage:
    if role == "system":
        return SystemMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    return HumanMessage(content=content)


def _model_config(state: AgentRuntimeState | dict[str, Any]) -> dict[str, Any]:
    model_config = state.get("model_config")
    if not isinstance(model_config, Mapping):
        raise CompactionError("llm_error", "压缩失败，当前请求已中止")
    return dict(model_config)


def _summary_from_response(response: Any) -> str:
    content = getattr(response, "content", "")
    summary = _sanitize_surrogates(_content_to_text(content).strip()).strip()
    if not summary:
        raise CompactionError("compaction_empty_summary", "压缩结果为空")
    return summary


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return str(content)


def _sanitize_surrogates(value: str) -> str:
    return _SURROGATE_RE.sub("", value)


def _extract_usage(message: Any) -> dict[str, Any] | None:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage:
        return dict(usage)
    if usage is not None and hasattr(usage, "items"):
        usage_dict = dict(usage)
        if usage_dict:
            return usage_dict

    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        metadata_usage = response_metadata.get("usage") or response_metadata.get(
            "token_usage"
        )
        if isinstance(metadata_usage, dict) and metadata_usage:
            return dict(metadata_usage)
        if metadata_usage is not None and hasattr(metadata_usage, "items"):
            usage_dict = dict(metadata_usage)
            if usage_dict:
                return usage_dict
    return None


def _token_counts(usage: dict[str, Any] | None) -> tuple[int, int, int]:
    if not usage:
        return 0, 0, 0

    token_input = _first_int(usage, ("input_tokens", "prompt_tokens", "token_input"))
    token_output = _first_int(
        usage,
        ("output_tokens", "completion_tokens", "token_output"),
    )
    token_cache = _first_int(usage, ("cache_read_tokens", "token_cache"))

    input_details = usage.get("input_token_details")
    if token_cache == 0 and isinstance(input_details, Mapping):
        token_cache = _first_int(
            input_details,
            ("cache_read", "cached_tokens", "token_cache"),
        )

    return token_input, token_output, token_cache


def _usage_payload(
    *,
    usage: dict[str, Any] | None,
    session_id: str,
    task_id: str,
    trigger: CompactionTrigger,
    token_input: int,
    token_output: int,
    token_cache: int,
) -> dict[str, Any]:
    usage_dict = dict(usage or {})
    usage_dict.setdefault("input_tokens", token_input)
    usage_dict.setdefault("output_tokens", token_output)
    usage_dict.setdefault("cache_read_tokens", token_cache)
    return {
        "usage_kind": "compaction",
        "session_id": session_id,
        "task_id": task_id,
        "trigger": trigger,
        "usage": usage_dict,
        "token_input": token_input,
        "token_output": token_output,
        "token_cache": token_cache,
    }


def _first_int(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float):
            return max(int(value), 0)
    return 0


async def _emit_event(
    sink: EventSink | None,
    name: str,
    payload: dict[str, Any],
) -> None:
    if sink is None:
        return
    try:
        result = sink(name, payload)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.opt(exception=True).warning("Compaction event sink failed")


async def _emit_usage(
    sink: UsageSink | None,
    payload: dict[str, Any],
) -> None:
    if sink is None:
        return
    try:
        result = sink(payload)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.opt(exception=True).warning("Compaction usage sink failed")


async def _emit_error(
    sink: EventSink | None,
    *,
    session_id: str,
    task_id: str,
    trigger: CompactionTrigger,
    error: CompactionError,
) -> None:
    await _emit_event(
        sink,
        "agent:compaction_error",
        {
            "session_id": session_id,
            "task_id": task_id,
            "trigger": trigger,
            "code": error.code,
            "message": error.message,
        },
    )
