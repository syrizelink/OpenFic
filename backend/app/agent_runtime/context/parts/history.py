import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.helpers import compile_canonical_mentions
from app.agent_runtime.context.types import ContextMessage


_COMPACT_TOOL_RESULT_NAMES = {
    "write_chapter",
    "edit_chapter",
}


def _is_context_history_message(raw: dict) -> bool:
    display_channel = raw.get("display_channel", raw.get("displayChannel"))
    if display_channel == "hidden":
        return False

    message_type = raw.get("message_type", raw.get("messageType"))
    return message_type in {None, "", "message"}


def _compact_tool_result_content(
    content: Any,
    *,
    tool_name: str | None = None,
) -> str:
    if not isinstance(content, str):
        return str(content)

    parsed = _parse_tool_result(content)
    if parsed is None:
        return content

    effective_tool_name = tool_name or _string_value(parsed.get("tool_name"))
    if effective_tool_name not in _COMPACT_TOOL_RESULT_NAMES:
        return content

    error = _string_value(parsed.get("error"))
    compact = {
        "success": False if error else bool(parsed.get("success")),
        "tool_name": effective_tool_name,
        "message": (
            _string_value(parsed.get("message"))
            or _string_value(parsed.get("reason"))
            or error
        ),
    }
    word_count = parsed.get("word_count")
    if isinstance(word_count, int) and not isinstance(word_count, bool):
        compact["word_count"] = word_count
    return json.dumps(compact, ensure_ascii=False)


def _parse_tool_result(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, Mapping):
        return None
    return dict(parsed)


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: Any) -> int | None:
    return value if type(value) is int else None


def _raw_metadata(raw: dict) -> dict:
    metadata = raw.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _history_metadata(raw: dict, *, tool_name: str | None = None) -> dict:
    raw_metadata = _raw_metadata(raw)
    metadata: dict = {"part": "history"}
    if "kind" in raw:
        metadata["kind"] = raw["kind"]
    elif "kind" in raw_metadata:
        metadata["kind"] = raw_metadata["kind"]

    seq = _int_value(raw_metadata.get("seq"))
    if seq is not None:
        metadata["seq"] = seq

    raw_tool_name = _string_value(raw_metadata.get("tool_name"))
    if tool_name or raw_tool_name:
        metadata["tool_name"] = tool_name or raw_tool_name
    return metadata


async def build_history(
    node_messages: list[dict],
    db_session: AsyncSession | None = None,
) -> list[ContextMessage]:
    """构建 p6 History 上下文片段，只保留真实对话消息。"""
    result: list[ContextMessage] = []
    for raw in node_messages:
        if not _is_context_history_message(raw):
            continue
        role = raw.get("role", "user")
        raw_metadata = _raw_metadata(raw)
        metadata_tool_name = _string_value(raw_metadata.get("tool_name"))
        name = raw.get("name") if isinstance(raw.get("name"), str) else None
        name = name or metadata_tool_name
        metadata = _history_metadata(raw, tool_name=name if role == "tool" else None)
        content = raw.get("content", "")
        if role == "tool":
            content = _compact_tool_result_content(content, tool_name=name)
        elif role == "user" and db_session is not None and isinstance(content, str) and "<of-mention" in content:
            content = await compile_canonical_mentions(content, db_session)
        result.append(ContextMessage(
            role=role,
            content=content,
            name=name,
            tool_call_id=raw.get("tool_call_id"),
            tool_calls=raw.get("tool_calls"),
            additional_kwargs=raw.get("additional_kwargs")
            if isinstance(raw.get("additional_kwargs"), dict)
            else None,
            metadata=metadata,
        ))
    return result
