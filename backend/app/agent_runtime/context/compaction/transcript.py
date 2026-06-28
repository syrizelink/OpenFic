from __future__ import annotations

from html import escape
import json
from typing import Any

from app.agent_runtime.context.types import ContextMessage


def _tool_call_name(tool_call: dict[str, Any]) -> str:
    name = tool_call.get("name")
    if isinstance(name, str) and name:
        return name

    function = tool_call.get("function")
    if isinstance(function, dict):
        function_name = function.get("name")
        if isinstance(function_name, str) and function_name:
            return function_name

    return "unknown"


def _tool_call_args(tool_call: dict[str, Any]) -> Any:
    if "args" in tool_call:
        return tool_call["args"]
    if "arguments" in tool_call:
        return _decode_arguments(tool_call["arguments"])

    function = tool_call.get("function")
    if isinstance(function, dict):
        if "args" in function:
            return function["args"]
        if "arguments" in function:
            return _decode_arguments(function["arguments"])

    return {}


def _decode_arguments(arguments: Any) -> Any:
    if not isinstance(arguments, str):
        return arguments
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return arguments


def _tool_name(message: ContextMessage) -> str:
    if message.name:
        return message.name

    metadata = message.metadata or {}
    metadata_name = metadata.get("tool_name")
    if isinstance(metadata_name, str) and metadata_name:
        return metadata_name

    return "unknown"


def _escape_xml_like(value: str) -> str:
    return escape(value, quote=True)


def _assistant_body(message: ContextMessage) -> str:
    parts = [_escape_xml_like(message.content or "")]
    for tool_call in message.tool_calls or []:
        name = _escape_xml_like(_tool_call_name(tool_call))
        args = json.dumps(
            _tool_call_args(tool_call),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        parts.append(f'<tool-call name="{name}">{_escape_xml_like(args)}</tool-call>')
    return "\n".join(part for part in parts if part)


def to_transcript(messages: list[ContextMessage]) -> str:
    parts: list[str] = []

    for message in messages:
        content = _escape_xml_like(message.content or "")
        if message.role == "user":
            parts.append(f"<user>{content}</user>")
        elif message.role == "assistant":
            parts.append(f"<assistant>{_assistant_body(message)}</assistant>")
        elif message.role == "tool":
            name = _escape_xml_like(_tool_name(message))
            parts.append(f'<tool name="{name}">{content}</tool>')

    return "\n".join(parts)
