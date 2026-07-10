import time

import pytest

from app.socket.handlers import (
    agent_subagent_session_room,
    agent_subagents_room,
    background_project_room,
    get_connection_state,
    is_connected,
)


class TestConnectionState:
    @pytest.fixture(autouse=True)
    def reset_state(self):
        state = get_connection_state()
        state.on_disconnect()
        yield
        state.on_disconnect()

    def test_initial_state_disconnected(self):
        state = get_connection_state()
        assert state.is_connected() is False
        assert state.sid is None

    def test_connect_updates_state(self):
        state = get_connection_state()
        state.on_connect("test_sid_123")
        assert state.is_connected() is True
        assert state.sid == "test_sid_123"
        assert state.connected_at is not None

    def test_disconnect_clears_state(self):
        state = get_connection_state()
        state.on_connect("test_sid_123")
        state.on_disconnect("test_sid_123")
        assert state.is_connected() is False
        assert state.sid is None

    def test_disconnect_keeps_other_clients_connected(self):
        state = get_connection_state()
        state.on_connect("first_sid")
        state.on_connect("second_sid")

        state.on_disconnect("second_sid")

        assert state.is_connected() is True
        assert state.sid == "first_sid"

    def test_heartbeat_updates_last_seen(self):
        state = get_connection_state()
        state.on_connect("test_sid_123")
        before = state.last_seen_at
        time.sleep(0.01)
        state.on_heartbeat()
        assert state.last_seen_at > before

    def test_is_connected_convenience_function(self):
        assert is_connected() is False
        state = get_connection_state()
        state.on_connect("test_sid")
        assert is_connected() is True


def test_background_project_room_formats_room_name():
    assert background_project_room("project-123") == "background:project:project-123"


def test_agent_subagents_room_formats_room_name():
    assert agent_subagents_room("parent-session-123") == "agent_subagents:parent-session-123"


def test_agent_subagent_session_room_formats_room_name():
    assert (
        agent_subagent_session_room("child-thread-123")
        == "agent_subagent_session:child-thread-123"
    )
