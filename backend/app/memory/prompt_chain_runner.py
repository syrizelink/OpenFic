# -*- coding: utf-8 -*-
"""
Prompt Chain Runner - 统一提示词链运行器。

用于按 mode/task/agent 获取提示词链版本、编译宏，并按 role 顺序注入 task context 消息。
"""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.macro.compiler import EntryInput, PromptChainCompiler
from app.storage.repos import task_message_repo
from app.storage.services import prompt_chain_service


THINKING_MESSAGE_TYPES = {"reasoning", "agent_thinking"}
UI_ONLY_MESSAGE_TYPES = {
    "approval",
    "node_end",
    "node_start",
    "question",
    "tool_approval_probe",
}
UI_ONLY_EVENT_TYPES = {"clarification", "tool_approval_required"}

AGENT_TOOL_NAMES: dict[str, set[str]] = {
    "explore": {"ask_user", "confirm_plan", "use_skill", "uninstall_skill"},
    "designer": {"confirm_outline", "use_skill", "uninstall_skill"},
    "writer": {"read_chapter", "create_chapter", "write_chapter", "edit_chapter", "delete_chapter", "use_skill", "uninstall_skill"},
    "reviewer": {"review_feedback", "use_skill", "uninstall_skill"},
}


def _parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _compact_tool_result(content: str, tool_call_id: str | None) -> dict[str, Any]:
    result = _parse_json_object(content)
    raw_metadata = result.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "tool_name": metadata.get("tool_name"),
        "success": result.get("success"),
        "message": result.get("message") or result.get("reason"),
    }


def _agent_role_header(agent_id: str | None) -> str:
    agent = agent_id or "unknown"
    return f"<agent_role>{agent}</agent_role>"


def _tool_calls_context(tool_calls: list[dict[str, Any]]) -> str:
    compact_calls = [
        {
            "name": item.get("name"),
            "args": item.get("args"),
        }
        for item in tool_calls
        if isinstance(item, dict)
    ]
    if not compact_calls:
        return ""
    return "历史工具调用结果上下文（不可作为当前Agent可用工具）：\n" + json.dumps(
        compact_calls,
        ensure_ascii=False,
    )


def _is_current_agent_tool_call(
    tool_calls: list[dict[str, Any]],
    current_agent_name: str | None,
) -> bool:
    if current_agent_name is None:
        return True
    allowed_tools = AGENT_TOOL_NAMES.get(current_agent_name, set())
    if not allowed_tools:
        return False
    return all(str(item.get("name") or "") in allowed_tools for item in tool_calls)


def _compact_task_history_message(
    message: Any,
    current_agent_name: str | None = None,
) -> dict[str, Any] | None:
    role = message.role
    metadata = _parse_json_object(message.message_metadata)
    event_type = metadata.get("event_type")

    if message.display_channel == "hidden":
        return None

    if message.message_type in THINKING_MESSAGE_TYPES:
        return None

    if message.message_type in UI_ONLY_MESSAGE_TYPES:
        return None

    if event_type in UI_ONLY_EVENT_TYPES:
        return None

    if role == "tool":
        compact_result = _compact_tool_result(message.content, message.tool_call_id)
        if current_agent_name is None or message.agent_id == current_agent_name:
            return compact_result
        return {
            "role": "assistant",
            "content": "\n".join(
                part
                for part in (
                    _agent_role_header(message.agent_id),
                    f"工具结果上下文：{compact_result.get('tool_name') or 'tool'} - {compact_result.get('message') or ''}",
                )
                if part
            ),
            "agent_id": message.agent_id,
        }

    payload: dict[str, Any] = {
        "role": role,
        "content": message.content,
    }
    if message.message_type:
        payload["message_type"] = message.message_type
    if message.agent_id:
        payload["agent_id"] = message.agent_id

    tool_calls = json.loads(message.tool_calls or "[]")
    if isinstance(tool_calls, list) and tool_calls:
        compact_tool_calls = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "args": item.get("args"),
            }
            for item in tool_calls
            if isinstance(item, dict)
        ]
        if _is_current_agent_tool_call(compact_tool_calls, current_agent_name):
            payload["tool_calls"] = compact_tool_calls
        else:
            context = _tool_calls_context(compact_tool_calls)
            payload["content"] = "\n".join(
                part
                for part in (
                    _agent_role_header(message.agent_id),
                    str(payload.get("content") or ""),
                    context,
                )
                if part
            )

    if role == "assistant" and event_type in {"confirmed_plan", "outline"}:
        payload["content"] = str(message.content).splitlines()[0][:300]
        payload["event_type"] = event_type

    reasoning_content = metadata.get("reasoning_content")
    if role == "assistant" and isinstance(reasoning_content, str) and reasoning_content:
        payload["reasoning_content"] = reasoning_content

    return payload


def _compact_task_history(
    messages: list[Any],
    current_agent_name: str | None = None,
) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    pending_tool_call_ids: set[str] = set()
    for message in messages:
        compact = _compact_task_history_message(message, current_agent_name)
        if compact is not None:
            compacted.append(compact)
            if compact.get("role") == "assistant" and compact.get("tool_calls"):
                pending_tool_call_ids.update(
                    str(tool_call.get("id") or "")
                    for tool_call in compact.get("tool_calls") or []
                    if isinstance(tool_call, dict) and tool_call.get("id")
                )
            elif compact.get("role") == "tool":
                pending_tool_call_ids.discard(str(compact.get("tool_call_id") or ""))
    if not pending_tool_call_ids:
        return compacted
    return [
        message
        for message in compacted
        if not (
            message.get("role") == "assistant"
            and any(
                isinstance(tool_call, dict) and str(tool_call.get("id") or "") in pending_tool_call_ids
                for tool_call in message.get("tool_calls") or []
            )
        )
    ]


def _filter_agent_local_history(
    messages: list[Any],
    *,
    agent_name: str,
    revision_id: str | None,
) -> list[Any]:
    filtered = []
    for message in messages:
        if message.agent_id != agent_name:
            continue
        if revision_id:
            metadata = _parse_json_object(message.message_metadata)
            if metadata.get("revision_id") != revision_id:
                continue
        filtered.append(message)
    return filtered


def _last_user_message_content(messages: list[dict[str, Any]]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") == "user" and not msg.get("tool_calls"):
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return None


@dataclass
class ChatRuntime:
    """Chat 运行时输入。"""

    current_message: str
    task_id: str | None = None
    history_agent_name: str | None = None
    history_revision_id: str | None = None
    anchor_chapter_id: str | None = None
    chat_history: list[dict[str, str]] = field(default_factory=list)
    rules_messages: list[dict[str, Any]] = field(default_factory=list)
    memory_messages: list[dict[str, Any]] = field(default_factory=list)
    skill_messages: list[dict[str, Any]] = field(default_factory=list)
    handoff_messages: list[dict[str, Any]] = field(default_factory=list)


async def build_chat_messages(
    session: AsyncSession,
    *,
    prompt_id: str,
    runtime: ChatRuntime,
) -> list[dict[str, Any]]:
    """
    构建 Chat 运行时消息列表。

    1. 加载并编译 prompt-chain。
    2. 追加 chat_history（chat 模式）。
    3. 追加 task context（agent 模式，来自 task_message_repo）。
    4. 追加当前用户消息（避免与历史重复）。
    """
    version_entries = await prompt_chain_service.get_latest_version_with_entries_or_default(
        session, prompt_id
    )

    entry_inputs = [
        EntryInput(
            role=e.role,
            content=e.content,
            order_index=e.order_index,
            is_enabled=e.is_enabled,
        )
        for e in version_entries.entries
    ]

    compiler = PromptChainCompiler()
    compile_result = await compiler.compile(entries=entry_inputs)

    messages: list[dict[str, Any]] = []
    for entry in compile_result.entries:
        if not entry.content:
            continue
        messages.append({"role": entry.role, "content": entry.content})

    if runtime.rules_messages:
        messages.extend(runtime.rules_messages)

    if runtime.memory_messages:
        messages.extend(runtime.memory_messages)

    if runtime.skill_messages:
        messages.extend(runtime.skill_messages)

    if runtime.handoff_messages:
        messages.extend(runtime.handoff_messages)

    if runtime.chat_history:
        for msg in runtime.chat_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    if runtime.task_id and runtime.history_agent_name:
        raw_task_messages = await task_message_repo.list_by_task(session, runtime.task_id)
        local_history = _filter_agent_local_history(
            raw_task_messages,
            agent_name=runtime.history_agent_name,
            revision_id=runtime.history_revision_id,
        )
        messages.extend(_compact_task_history(local_history, runtime.history_agent_name))

    if runtime.current_message:
        last_user = _last_user_message_content(messages)
        if last_user != runtime.current_message:
            messages.append({"role": "user", "content": runtime.current_message})

    return messages
