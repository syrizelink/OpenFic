from typing import Any

from app.socket.handlers import get_connection_state
from app.socket.server import sio


async def emit(
    event: str,
    data: dict[str, Any],
    *,
    room: str | None = None,
) -> None:
    """向前端推送事件。无连接时静默丢弃，可指定 Socket.IO 房间。"""
    if room:
        await sio.emit(event, data, room=room)
        return

    state = get_connection_state()
    if not state.is_connected():
        return
    await sio.emit(event, data, to=state.sid)
