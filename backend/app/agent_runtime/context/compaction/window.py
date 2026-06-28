from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from app.agent_runtime.context.compaction.config import (
    MIN_COMPACTABLE_TOKENS,
    TAIL_TOKEN_BUDGET,
    TAIL_WINDOW_RATIO,
)
from app.agent_runtime.context.compaction.tokens import count_context_tokens
from app.agent_runtime.context.compaction.transcript import to_transcript
from app.agent_runtime.context.compaction.turns import LLMTurn, group_llm_turns
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.persistence.compaction_types import PersistedCompaction


class CompactionNoWindowError(Exception):
    code = "no_compactable_window"


@dataclass(frozen=True)
class CompactionWindow:
    start_seq: int
    end_seq: int
    messages: list[ContextMessage]
    source_input_tokens: int
    transcript: str


def _seq(message: ContextMessage) -> int | None:
    seq = (message.metadata or {}).get("seq")
    if type(seq) is int:
        return seq
    return None


def _raise_no_window() -> NoReturn:
    raise CompactionNoWindowError(CompactionNoWindowError.code)


def _lower_bound(
    history_messages: list[ContextMessage],
    existing_compactions: list[PersistedCompaction],
) -> int:
    if existing_compactions:
        return max(compaction.end_seq for compaction in existing_compactions) + 1

    for message in history_messages:
        if message.role == "user" and (seq := _seq(message)) is not None:
            return seq + 1

    _raise_no_window()


def _turn_tokens(turn: LLMTurn) -> int:
    return count_context_tokens(turn.messages)


def _tail_start_index(turns: list[LLMTurn], tail_budget: int) -> int:
    tail_start = len(turns)
    tail_tokens = 0

    for index in range(len(turns) - 1, -1, -1):
        turn_tokens = _turn_tokens(turns[index])
        if tail_start == len(turns):
            tail_tokens += turn_tokens
            tail_start = index
            continue
        if tail_tokens + turn_tokens > tail_budget:
            break
        tail_tokens += turn_tokens
        tail_start = index

    return tail_start


def select_compaction_window(
    history_messages: list[ContextMessage],
    existing_compactions: list[PersistedCompaction],
    max_context_tokens: int,
) -> CompactionWindow:
    lower_bound = _lower_bound(history_messages, existing_compactions)
    sequenced_messages = [
        message
        for message in history_messages
        if (seq := _seq(message)) is not None and seq >= lower_bound
    ]
    turns = group_llm_turns(sequenced_messages)
    if len(turns) < 2:
        _raise_no_window()

    tail_budget = min(TAIL_TOKEN_BUDGET, int(max_context_tokens * TAIL_WINDOW_RATIO))
    tail_start = _tail_start_index(turns, tail_budget)
    window_turns = turns[:tail_start]
    if not window_turns:
        _raise_no_window()

    window_messages = [
        message for turn in window_turns for message in turn.messages
    ]
    source_input_tokens = count_context_tokens(window_messages)
    if source_input_tokens < MIN_COMPACTABLE_TOKENS:
        _raise_no_window()

    seqs = [seq for message in window_messages if (seq := _seq(message)) is not None]
    if not seqs:
        _raise_no_window()

    return CompactionWindow(
        start_seq=min(seqs),
        end_seq=max(seqs),
        messages=window_messages,
        source_input_tokens=source_input_tokens,
        transcript=to_transcript(window_messages),
    )
