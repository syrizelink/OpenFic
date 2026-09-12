from typing import Any

from app.socket.handlers import get_connection_state
from app.socket.server import sio


async def emit(
    event: str,
    data: dict[str, Any],
    *,
    room: str | None = None,
) -> None:
    """Mengirim event ke frontend. Diabaikan diam-diam bila tidak ada koneksi, dan ruang Socket.IO dapat ditentukan."""
    if room:
        await sio.emit(event, data, room=room)
        return

    state = get_connection_state()
    if not state.is_connected():
        return
    await sio.emit(event, data)
