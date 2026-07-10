from unittest.mock import AsyncMock, patch

import pytest

from app.socket.emitter import emit
from app.socket.handlers import get_connection_state


class TestEmit:
    @pytest.fixture(autouse=True)
    def reset_state(self):
        state = get_connection_state()
        state.on_disconnect()
        yield
        state.on_disconnect()

    async def test_emit_when_connected(self):
        state = get_connection_state()
        state.on_connect("test_sid")

        with patch("app.socket.emitter.sio") as mock_sio:
            mock_sio.emit = AsyncMock()
            await emit("agent:token", {"content": "hello"})
            mock_sio.emit.assert_called_once_with("agent:token", {"content": "hello"})

    async def test_emit_broadcasts_when_multiple_clients_are_connected(self):
        state = get_connection_state()
        state.on_connect("first_sid")
        state.on_connect("second_sid")

        with patch("app.socket.emitter.sio") as mock_sio:
            mock_sio.emit = AsyncMock()
            await emit("agent:token", {"content": "hello"})
            mock_sio.emit.assert_called_once_with("agent:token", {"content": "hello"})

    async def test_emit_when_disconnected_does_nothing(self):
        with patch("app.socket.emitter.sio") as mock_sio:
            mock_sio.emit = AsyncMock()
            await emit("agent:token", {"content": "hello"})
            mock_sio.emit.assert_not_called()

    async def test_emit_with_empty_data(self):
        state = get_connection_state()
        state.on_connect("test_sid")

        with patch("app.socket.emitter.sio") as mock_sio:
            mock_sio.emit = AsyncMock()
            await emit("heartbeat:ack", {})
            mock_sio.emit.assert_called_once_with("heartbeat:ack", {})

    async def test_emit_to_room(self):
        with patch("app.socket.emitter.sio") as mock_sio:
            mock_sio.emit = AsyncMock()
            await emit("agent:token", {"content": "hello"}, room="agent_session:s1")
            mock_sio.emit.assert_called_once_with(
                "agent:token", {"content": "hello"}, room="agent_session:s1"
            )
