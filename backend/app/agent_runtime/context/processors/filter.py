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
    """过滤无效的 history 消息，保护工具调用配对。p1-p5 原样保留。"""
    # 第一轮：标记基础有效性
    keep: list[bool] = []
    for m in parts:
        if not _is_history(m):
            keep.append(True)
            continue
        if (
            (not m.content or not m.content.strip())
            and not (m.role == "assistant" and m.tool_calls)
        ):
            keep.append(False)
            continue
        if _kind(m) in _DROPPED_KINDS:
            keep.append(False)
            continue
        keep.append(True)

    # 第二轮：处理孤立的 assistant.tool_calls
    # 收集仍保留的 assistant 工具调用 id 集合 与 tool 响应 id 集合
    assistant_call_ids: set[str] = set()
    tool_response_ids: set[str] = set()
    for m, k in zip(parts, keep):
        if not k or not _is_history(m):
            continue
        if m.role == "assistant" and m.tool_calls:
            for c in m.tool_calls:
                cid = c.get("id")
                if cid:
                    assistant_call_ids.add(cid)
        elif m.role == "tool" and m.tool_call_id:
            tool_response_ids.add(m.tool_call_id)

    orphan_call_ids = assistant_call_ids - tool_response_ids

    # 第三轮：丢弃孤立 assistant 与孤立 tool 响应
    for i, m in enumerate(parts):
        if not keep[i] or not _is_history(m):
            continue
        if m.role == "assistant" and m.tool_calls:
            ids = {c.get("id") for c in m.tool_calls if c.get("id")}
            if ids and ids.issubset(orphan_call_ids):
                keep[i] = False
        elif m.role == "tool" and m.tool_call_id:
            if m.tool_call_id not in assistant_call_ids:
                keep[i] = False

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
