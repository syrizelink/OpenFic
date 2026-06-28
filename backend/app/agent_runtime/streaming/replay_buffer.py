from __future__ import annotations

import asyncio
import copy
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator


BUFFERED_AGENT_EVENT_NAMES = {
    "agent:node",
    "agent:subagent_status",
    "agent:token",
    "agent:reasoning",
    "agent:tool_call",
    "agent:retry",
    "agent:compaction_start",
    "agent:compaction_success",
    "agent:compaction_error",
}

COMPACTION_TERMINAL_EVENT_NAMES = {
    "agent:compaction_success",
    "agent:compaction_error",
}


@dataclass(frozen=True)
class BufferedAgentEvent:
    name: str
    data: dict[str, Any]


class AgentEventReplayBuffer:
    def __init__(self, max_events_per_session: int = 1000) -> None:
        self._events: dict[str, list[BufferedAgentEvent]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._max_events_per_session = max_events_per_session

    @asynccontextmanager
    async def session_lock(self, session_id: str) -> AsyncIterator[None]:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            yield

    def record_unlocked(self, name: str, data: dict[str, Any]) -> None:
        if name not in BUFFERED_AGENT_EVENT_NAMES:
            return
        session_id = self._buffer_session_id(name, data)
        if session_id is None:
            return

        events = self._events.setdefault(session_id, [])
        if name == "agent:retry":
            events[:] = [event for event in events if event.name != name]
        if name in COMPACTION_TERMINAL_EVENT_NAMES:
            events[:] = [
                event
                for event in events
                if event.name != "agent:compaction_start"
            ]
        if name == "agent:subagent_status":
            child_run_id = data.get("child_run_id")
            if isinstance(child_run_id, str) and child_run_id:
                events[:] = [
                    event
                    for event in events
                    if not (
                        event.name == name
                        and event.data.get("child_run_id") == child_run_id
                    )
                ]
        events.append(BufferedAgentEvent(name=name, data=copy.deepcopy(data)))
        if len(events) > self._max_events_per_session:
            del events[: len(events) - self._max_events_per_session]

    @staticmethod
    def _buffer_session_id(name: str, data: dict[str, Any]) -> str | None:
        if name == "agent:subagent_status":
            value = data.get("parent_session_id")
            return value if isinstance(value, str) and value else None
        value = data.get("session_id")
        return value if isinstance(value, str) and value else None

    def replay_events_unlocked(self, session_id: str) -> list[BufferedAgentEvent]:
        return [
            BufferedAgentEvent(name=event.name, data=copy.deepcopy(event.data))
            for event in self._events.get(session_id, [])
        ]

    def clear_run_unlocked(self, session_id: str, run_id: object) -> None:
        if not isinstance(run_id, str) or not run_id:
            return
        events = self._events.get(session_id)
        if not events:
            return
        self._events[session_id] = [
            event for event in events if event.data.get("run_id") != run_id
        ]
        if not self._events[session_id]:
            self._events.pop(session_id, None)

    def clear_event_unlocked(self, session_id: str, name: str) -> None:
        events = self._events.get(session_id)
        if not events:
            return
        self._events[session_id] = [event for event in events if event.name != name]
        if not self._events[session_id]:
            self._events.pop(session_id, None)

    def clear_session_unlocked(self, session_id: str) -> None:
        self._events.pop(session_id, None)

    def clear_all(self) -> None:
        self._events.clear()
        self._locks.clear()


_AGENT_EVENT_REPLAY_BUFFER = AgentEventReplayBuffer()


def get_agent_event_replay_buffer() -> AgentEventReplayBuffer:
    return _AGENT_EVENT_REPLAY_BUFFER
