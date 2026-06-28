import importlib

import pytest


def _load_node_events_module():
    try:
        return importlib.import_module("app.agent_runtime.graph.node_events")
    except ModuleNotFoundError:
        pytest.fail("node event helper is missing")


@pytest.mark.asyncio
async def test_wrap_node_emits_start_and_end_events(monkeypatch):
    node_events = _load_node_events_module()
    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name: str, data: dict, room: str | None = None) -> None:
        emitted.append((name, data, room))

    monkeypatch.setattr(node_events, "emit", fake_emit)

    async def inner_node(state: dict, config: dict | None = None) -> dict:
        return {"active_agent": "composer"}

    wrapped = node_events.with_node_events("composer", inner_node)
    result = await wrapped(
        {"session_id": "sess_001"},
        {"configurable": {"runtime_context": {}}},
    )

    assert result == {"active_agent": "composer"}
    assert emitted == [
        (
            "agent:node",
            {
                "session_id": "sess_001",
                "node": "composer",
                "phase": "start",
                "status": "running",
                "current_node": "composer",
                "previous_node": None,
            },
            "agent_session:sess_001",
        ),
        (
            "agent:node",
            {
                "session_id": "sess_001",
                "node": "composer",
                "phase": "end",
                "status": "completed",
                "current_node": None,
                "previous_node": None,
            },
            "agent_session:sess_001",
        ),
    ]


@pytest.mark.asyncio
async def test_wrap_node_emits_error_end_event(monkeypatch):
    node_events = _load_node_events_module()
    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name: str, data: dict, room: str | None = None) -> None:
        emitted.append((name, data, room))

    monkeypatch.setattr(node_events, "emit", fake_emit)

    async def inner_node(state: dict, config: dict | None = None) -> dict:
        raise RuntimeError("boom")

    wrapped = node_events.with_node_events("writer", inner_node)

    with pytest.raises(RuntimeError, match="boom"):
        await wrapped(
            {"session_id": "sess_001"},
            {"configurable": {"runtime_context": {}}},
        )

    assert emitted[-1] == (
        "agent:node",
        {
            "session_id": "sess_001",
            "node": "writer",
            "phase": "end",
            "status": "error",
            "current_node": None,
            "previous_node": None,
        },
        "agent_session:sess_001",
    )


@pytest.mark.asyncio
async def test_wrap_node_reports_previous_node_on_next_start(monkeypatch):
    node_events = _load_node_events_module()
    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name: str, data: dict, room: str | None = None) -> None:
        emitted.append((name, data, room))

    monkeypatch.setattr(node_events, "emit", fake_emit)

    async def inner_node(state: dict, config: dict | None = None) -> dict:
        return {}

    config = {"configurable": {"runtime_context": {}}}
    await node_events.with_node_events("clarifier", inner_node)(
        {"session_id": "sess_001"},
        config,
    )
    await node_events.with_node_events("composer", inner_node)(
        {"session_id": "sess_001"},
        config,
    )

    composer_start = next(
        payload
        for name, payload, _room in emitted
        if name == "agent:node"
        and payload["node"] == "composer"
        and payload["phase"] == "start"
    )
    assert composer_start["current_node"] == "composer"
    assert composer_start["previous_node"] == "clarifier"


@pytest.mark.asyncio
async def test_emit_node_event_forwards_payload_to_configured_sink(monkeypatch):
    node_events = _load_node_events_module()
    persisted: list[dict] = []

    async def fake_emit(name: str, data: dict, room: str | None = None) -> None:
        return None

    async def node_event_sink(payload: dict) -> None:
        persisted.append(payload)

    monkeypatch.setattr(node_events, "emit", fake_emit)

    await node_events.emit_node_event(
        {
            "configurable": {
                "runtime_context": {},
                "node_event_sink": node_event_sink,
            }
        },
        session_id="sess_001",
        node="composer",
        phase="start",
        status="running",
    )

    assert persisted == [
        {
            "session_id": "sess_001",
            "node": "composer",
            "phase": "start",
            "status": "running",
            "current_node": "composer",
            "previous_node": None,
        }
    ]


@pytest.mark.asyncio
async def test_emit_node_event_uses_subagent_session_room_for_child_events(monkeypatch):
    node_events = _load_node_events_module()
    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name: str, data: dict, room: str | None = None) -> None:
        emitted.append((name, data, room))

    monkeypatch.setattr(node_events, "emit", fake_emit)

    await node_events.emit_node_event(
        {
            "tags": ["subagent_child"],
            "configurable": {"runtime_context": {}},
        },
        session_id="child-thread-1",
        node="writer",
        phase="start",
        status="running",
    )

    assert emitted == [
        (
            "agent:node",
            {
                "session_id": "child-thread-1",
                "node": "writer",
                "phase": "start",
                "status": "running",
                "current_node": "writer",
                "previous_node": None,
            },
            "agent_subagent_session:child-thread-1",
        )
    ]
