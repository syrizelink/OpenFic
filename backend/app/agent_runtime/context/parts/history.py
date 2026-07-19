from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.helpers import compile_canonical_mentions
from app.agent_runtime.context.types import ContextMessage

def _is_context_history_message(raw: dict) -> bool:
    display_channel = raw.get("display_channel", raw.get("displayChannel"))
    if display_channel == "hidden":
        return False

    message_type = raw.get("message_type", raw.get("messageType"))
    return message_type in {None, "", "message"}

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
        if role == "user" and db_session is not None and isinstance(content, str) and "<of-mention" in content:
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
