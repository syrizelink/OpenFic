import json
from dataclasses import replace
from typing import Any

from app.agent_runtime.context.types import ContextMessage

_DROPPED_KINDS = {"thinking", "reasoning", "ui_only"}


def _is_history(m: ContextMessage) -> bool:
    return (m.metadata or {}).get("part") == "history"


def _kind(m: ContextMessage) -> str | None:
    return (m.metadata or {}).get("kind")


def filter_invalid(parts: list[ContextMessage]) -> list[ContextMessage]:
    """过滤无效 history，并保留符合工具调用协议的连续消息组。"""
    keep: list[bool] = []
    for m in parts:
        if not _is_history(m):
            keep.append(True)
            continue
        if (not m.content or not m.content.strip()) and not m.attachments and not (
            m.role == "assistant" and m.tool_calls
        ):
            keep.append(False)
            continue
        if _kind(m) in _DROPPED_KINDS:
            keep.append(False)
            continue
        keep.append(True)

    pending_assistant_index: int | None = None
    pending_assistant: ContextMessage | None = None
    pending_tool_call_ids: set[str] = set()
    pending_tool_indices: list[int] = []

    def drop_pending_group() -> None:
        nonlocal \
            pending_assistant_index, \
            pending_assistant, \
            pending_tool_call_ids, \
            pending_tool_indices
        if pending_assistant_index is not None and pending_assistant is not None:
            completed_tool_call_ids = {
                parts[tool_index].tool_call_id
                for tool_index in pending_tool_indices
                if parts[tool_index].tool_call_id
            }
            completed_tool_calls = [
                tool_call
                for tool_call in pending_assistant.tool_calls or []
                if tool_call.get("id") in completed_tool_call_ids
            ]
            if completed_tool_calls:
                parts[pending_assistant_index] = replace(
                    pending_assistant,
                    tool_calls=completed_tool_calls,
                )
            else:
                keep[pending_assistant_index] = False
                for tool_index in pending_tool_indices:
                    keep[tool_index] = False
        pending_assistant_index = None
        pending_assistant = None
        pending_tool_call_ids = set()
        pending_tool_indices = []

    for index, message in enumerate(parts):
        if not keep[index] or not _is_history(message):
            drop_pending_group()
            continue

        if pending_assistant_index is not None:
            if message.role == "tool" and message.tool_call_id in pending_tool_call_ids:
                pending_tool_call_ids.remove(message.tool_call_id)
                pending_tool_indices.append(index)
                if not pending_tool_call_ids:
                    pending_assistant_index = None
                    pending_assistant = None
                    pending_tool_indices = []
                continue
            drop_pending_group()

        if message.role == "assistant" and message.tool_calls:
            tool_call_ids = [
                tool_call_id
                for tool_call in message.tool_calls
                if isinstance(tool_call_id := tool_call.get("id"), str) and tool_call_id
            ]
            if len(tool_call_ids) != len(message.tool_calls) or len(
                set(tool_call_ids)
            ) != len(tool_call_ids):
                keep[index] = False
                continue
            pending_assistant_index = index
            pending_assistant = message
            pending_tool_call_ids = set(tool_call_ids)
            pending_tool_indices = []
            continue

        if message.role == "tool":
            keep[index] = False

    drop_pending_group()

    return [m for m, k in zip(parts, keep) if k]


def filter_tool_result_metadata(parts: list[ContextMessage]) -> list[ContextMessage]:
    """移除仅供界面消费的工具结果 metadata，避免将其发送给模型。"""
    result: list[ContextMessage] = []
    for message in parts:
        if message.role != "tool":
            result.append(message)
            continue
        visible_content = filter_tool_result_metadata_content(message.content)
        if visible_content == message.content:
            result.append(message)
            continue
        result.append(
            replace(
                message,
                content=visible_content,
            )
        )
    return result


def _parse_tool_result(content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def filter_tool_result_metadata_content(content: str) -> str:
    """返回可发送给模型的工具结果内容。"""
    payload = _parse_tool_result(content)
    if payload is None or "metadata" not in payload:
        return content
    return json.dumps(
        {key: value for key, value in payload.items() if key != "metadata"},
        ensure_ascii=False,
    )
