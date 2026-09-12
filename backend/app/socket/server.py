import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=20,
    logger=False,
    engineio_logger=False,
)


def init_socketio(app: FastAPI) -> socketio.ASGIApp:
    """Memasang Socket.IO ke FastAPI dan mengembalikan ASGI app hasil pembungkusan."""
    from app.socket.handlers import register_handlers

    register_handlers(sio)
    return socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")
