import time
from dataclasses import dataclass, field

import socketio  # type: ignore[import-untyped]
from loguru import logger

from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.api.routers.chapter_context import build_summary_realtime_snapshot
from app.core.errors import NotFoundError
from app.storage.database import create_session
from app.storage.services import task_service


@dataclass
class ConnectionState:
    """单用户连接状态。"""

    sid: str | None = None
    connected_at: float | None = None
    last_seen_at: float = field(default_factory=time.time)

    def is_connected(self) -> bool:
        return self.sid is not None

    def on_connect(self, sid: str) -> None:
        self.sid = sid
        self.connected_at = time.time()
        self.last_seen_at = self.connected_at

    def on_disconnect(self) -> None:
        self.sid = None
        self.connected_at = None

    def on_heartbeat(self) -> None:
        self.last_seen_at = time.time()


_state = ConnectionState()


def get_connection_state() -> ConnectionState:
    return _state


def is_connected() -> bool:
    """前端当前是否在线。"""
    return _state.is_connected()


def agent_session_room(session_id: str) -> str:
    return f"agent_session:{session_id}"


def agent_subagent_session_room(child_thread_id: str) -> str:
    return f"agent_subagent_session:{child_thread_id}"


def agent_subagents_room(session_id: str) -> str:
    return f"agent_subagents:{session_id}"


def background_project_room(project_id: str) -> str:
    return f"background:project:{project_id}"


def register_handlers(sio: socketio.AsyncServer) -> None:
    """注册所有客户端→服务端事件处理器。"""

    @sio.event
    async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
        logger.info(f"Client connected: {sid}")
        _state.on_connect(sid)

    @sio.event
    async def disconnect(sid: str) -> None:
        logger.info(f"Client disconnected: {sid}")
        _state.on_disconnect()

    @sio.on("heartbeat")
    async def heartbeat(sid: str, data: dict | None = None) -> None:
        _state.on_heartbeat()

    @sio.on("agent:join")
    async def agent_join(sid: str, data: dict | None = None) -> None:
        session_id = (data or {}).get("session_id")
        if not isinstance(session_id, str) or not session_id:
            await sio.emit(
                "agent:error",
                {"type": "invalid_session", "reason": "session_id is required"},
                to=sid,
            )
            return
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(session_id):
            await sio.enter_room(sid, agent_session_room(session_id))
            await sio.emit("agent:joined", {"session_id": session_id}, to=sid)
            session = await create_session()
            try:
                try:
                    task = await task_service.get_task_by_agent_session_id(
                        session,
                        session_id,
                    )
                except NotFoundError:
                    task = None
            finally:
                await session.close()
            if task is not None:
                await sio.emit(
                    "agent:task_usage_snapshot",
                    {
                        "session_id": session_id,
                        "task_id": task.id,
                        "token_input": int(task.token_input),
                        "token_output": int(task.token_output),
                        "token_cache": int(task.token_cache),
                    },
                    to=sid,
                )
            for event in buffer.replay_events_unlocked(session_id):
                if event.name == "agent:subagent_status":
                    continue
                await sio.emit(event.name, event.data, to=sid)

    @sio.on("agent:join_subagent")
    async def agent_join_subagent(sid: str, data: dict | None = None) -> None:
        child_thread_id = (data or {}).get("child_thread_id")
        if not isinstance(child_thread_id, str) or not child_thread_id:
            await sio.emit(
                "agent:error",
                {"type": "invalid_child_thread", "reason": "child_thread_id is required"},
                to=sid,
            )
            return
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(child_thread_id):
            await sio.enter_room(sid, agent_subagent_session_room(child_thread_id))
            await sio.emit(
                "agent:joined_subagent",
                {"child_thread_id": child_thread_id},
                to=sid,
            )
            for event in buffer.replay_events_unlocked(child_thread_id):
                await sio.emit(event.name, event.data, to=sid)

    @sio.on("agent:join_subagents")
    async def agent_join_subagents(sid: str, data: dict | None = None) -> None:
        session_id = (data or {}).get("session_id")
        if not isinstance(session_id, str) or not session_id:
            await sio.emit(
                "agent:error",
                {
                    "type": "invalid_session",
                    "reason": "session_id is required",
                },
                to=sid,
            )
            return
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock(session_id):
            await sio.enter_room(sid, agent_subagents_room(session_id))
            await sio.emit(
                "agent:joined_subagents",
                {"session_id": session_id},
                to=sid,
            )
            for event in buffer.replay_events_unlocked(session_id):
                if event.name == "agent:subagent_status":
                    await sio.emit(event.name, event.data, to=sid)

    @sio.on("agent:leave")
    async def agent_leave(sid: str, data: dict | None = None) -> None:
        session_id = (data or {}).get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return
        await sio.leave_room(sid, agent_session_room(session_id))
        await sio.emit("agent:left", {"session_id": session_id}, to=sid)

    @sio.on("agent:leave_subagent")
    async def agent_leave_subagent(sid: str, data: dict | None = None) -> None:
        child_thread_id = (data or {}).get("child_thread_id")
        if not isinstance(child_thread_id, str) or not child_thread_id:
            return
        await sio.leave_room(sid, agent_subagent_session_room(child_thread_id))
        await sio.emit(
            "agent:left_subagent",
            {"child_thread_id": child_thread_id},
            to=sid,
        )

    @sio.on("agent:leave_subagents")
    async def agent_leave_subagents(sid: str, data: dict | None = None) -> None:
        session_id = (data or {}).get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return
        await sio.leave_room(sid, agent_subagents_room(session_id))
        await sio.emit(
            "agent:left_subagents",
            {"session_id": session_id},
            to=sid,
        )

    @sio.on("background:join")
    async def background_join(sid: str, data: dict | None = None) -> None:
        project_id = (data or {}).get("project_id")
        if not isinstance(project_id, str) or not project_id:
            await sio.emit(
                "background:error",
                {"type": "invalid_project", "reason": "project_id is required"},
                to=sid,
            )
            return
        await sio.enter_room(sid, background_project_room(project_id))
        await sio.emit("background:joined", {"project_id": project_id}, to=sid)
        session = await create_session()
        try:
            snapshot = await build_summary_realtime_snapshot(
                session,
                project_id,
                time.time_ns(),
            )
            await sio.emit(
                "background:snapshot",
                snapshot.model_dump(mode="json"),
                to=sid,
            )
        finally:
            await session.close()

    @sio.on("background:leave")
    async def background_leave(sid: str, data: dict | None = None) -> None:
        project_id = (data or {}).get("project_id")
        if not isinstance(project_id, str) or not project_id:
            return
        await sio.leave_room(sid, background_project_room(project_id))
        await sio.emit("background:left", {"project_id": project_id}, to=sid)
