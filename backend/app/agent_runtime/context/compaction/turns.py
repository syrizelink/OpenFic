from __future__ import annotations

from dataclasses import dataclass

from app.agent_runtime.context.types import ContextMessage


@dataclass(frozen=True)
class LLMTurn:
    messages: list[ContextMessage]


def _tool_call_ids(message: ContextMessage) -> set[str]:
    return {
        tool_call_id
        for tool_call in message.tool_calls or []
        if isinstance(tool_call_id := tool_call.get("id"), str)
    }


def group_llm_turns(history_messages: list[ContextMessage]) -> list[LLMTurn]:
    turns: list[LLMTurn] = []
    current: list[ContextMessage] = []
    pending_tool_call_ids: set[str] = set()

    def flush() -> None:
        nonlocal current, pending_tool_call_ids
        if current:
            turns.append(LLMTurn(messages=current))
            current = []
            pending_tool_call_ids = set()

    for message in history_messages:
        if message.role == "assistant" and message.tool_calls:
            flush()
            current = [message]
            pending_tool_call_ids = _tool_call_ids(message)
            if not pending_tool_call_ids:
                flush()
            continue

        if (
            message.role == "tool"
            and message.tool_call_id
            and message.tool_call_id in pending_tool_call_ids
        ):
            current.append(message)
            pending_tool_call_ids.discard(message.tool_call_id)
            if not pending_tool_call_ids:
                flush()
            continue

        flush()
        turns.append(LLMTurn(messages=[message]))

    flush()
    return turns
