import asyncio
import socket

import pytest
import pytest_asyncio
import socketio as socketio_lib  # type: ignore[import-untyped]
import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.storage import database
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.socket import background_project_room, emit, is_connected, init_socketio
from app.socket.handlers import (
    agent_subagent_session_room,
    agent_subagents_room,
    get_connection_state,
)
from tests.model_registry import register_sqlmodel_models


@pytest_asyncio.fixture(loop_scope="function")
async def socket_db_factory():
    from sqlalchemy.pool import StaticPool

    register_sqlmodel_models()

    original_factory = database._async_session_factory
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    database._async_session_factory = factory
    try:
        yield factory
    finally:
        database._async_session_factory = original_factory
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def server(socket_db_factory):
    """Start a real ASGI server for integration testing."""
    port_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_socket.bind(("127.0.0.1", 0))
    port = port_socket.getsockname()[1]
    port_socket.close()

    test_app = FastAPI()
    asgi_app = init_socketio(test_app)

    # Avoid Uvicorn's legacy websockets backend, which emits deprecation warnings
    # with the installed websockets package.
    config = uvicorn.Config(
        asgi_app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        ws="websockets-sansio",
    )
    srv = uvicorn.Server(config)

    task = asyncio.create_task(srv.serve())
    # Wait for server to be ready
    while not srv.started:
        await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    await task

    # Reset state after test
    get_connection_state().on_disconnect()


async def _seed_project(
    socket_db_factory,
    *,
    project_id: str,
    chapter_id: str,
    status: str | None = None,
) -> None:
    async with socket_db_factory() as session:
        project = Project(id=project_id, title=f"项目 {project_id}", description="")
        volume = Volume(
            id=f"{project_id}-volume-1",
            project_id=project_id,
            title="第一卷",
            order=1,
            chapter_count=1,
        )
        chapter = Chapter(
            id=chapter_id,
            project_id=project_id,
            volume_id=volume.id,
            title=f"章节 {chapter_id}",
            content="正文" * 400,
            word_count=800,
            order=1,
        )
        session.add(project)
        session.add(volume)
        session.add(chapter)
        if status is not None:
            session.add(
                ChapterSummary(
                    project_id=project_id,
                    summary_type="chapter",
                    status=status,
                    chapter_id=chapter_id,
                    chapter_order=1,
                    start_order=1,
                    end_order=1,
                )
            )
        await session.commit()


async def _expect_background_joined_and_snapshot(client, project_id: str):
    joined_event = await asyncio.wait_for(client.receive(), timeout=2.0)
    assert joined_event[0] == "background:joined"
    assert joined_event[1] == {"project_id": project_id}

    snapshot_event = await asyncio.wait_for(client.receive(), timeout=2.0)
    assert snapshot_event[0] == "background:snapshot"
    snapshot = snapshot_event[1]
    assert snapshot["project_id"] == project_id
    assert isinstance(snapshot["project_revision"], int)
    assert snapshot["project_revision"] > 0
    assert "summary" in snapshot
    assert "statuses" in snapshot["summary"]
    assert "maintenance" in snapshot["summary"]
    return snapshot


@pytest.fixture(autouse=True)
def reset_state():
    get_connection_state().on_disconnect()
    get_agent_event_replay_buffer().clear_all()
    yield
    get_connection_state().on_disconnect()
    get_agent_event_replay_buffer().clear_all()


class TestSocketIntegration:
    async def test_connect_and_disconnect(self, server):
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)
        assert is_connected() is True

        await client.disconnect()
        await asyncio.sleep(0.1)
        assert is_connected() is False

    async def test_emit_reaches_client(self, server):
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await emit("agent:token", {"content": "hello"})
        event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert event[0] == "agent:token"
        assert event[1] == {"content": "hello"}

        await client.disconnect()

    async def test_join_agent_session_room_receives_room_event(self, server):
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit("agent:join", {"session_id": "s1"})
        joined_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert joined_event[0] == "agent:joined"
        assert joined_event[1] == {"session_id": "s1"}

        await emit("agent:token", {"session_id": "s1", "content": "hello"}, room="agent_session:s1")
        event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert event[0] == "agent:token"
        assert event[1] == {"session_id": "s1", "content": "hello"}

        await client.disconnect()

    async def test_join_agent_session_replays_buffered_stream_events(self, server):
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock("s1"):
            buffer.record_unlocked(
                "agent:token",
                {"session_id": "s1", "run_id": "run-1", "content": "前半段"},
            )

        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit("agent:join", {"session_id": "s1"})
        joined_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert joined_event[0] == "agent:joined"
        assert joined_event[1] == {"session_id": "s1"}

        replayed_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert replayed_event[0] == "agent:token"
        assert replayed_event[1] == {
            "session_id": "s1",
            "run_id": "run-1",
            "content": "前半段",
        }

        await client.disconnect()

    async def test_join_subagents_replays_status_without_child_transcript(
        self,
        server,
    ):
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock("parent-session"):
            buffer.record_unlocked(
                "agent:subagent_status",
                {
                    "parent_session_id": "parent-session",
                    "child_run_id": "child-run-1",
                    "child_thread_id": "child-thread-1",
                    "agent_key": "writer",
                    "status": "running",
                    "queued_messages": 1,
                    "is_active": True,
                },
            )
        async with buffer.session_lock("child-thread-1"):
            buffer.record_unlocked(
                "agent:token",
                {
                    "session_id": "child-thread-1",
                    "run_id": "child-run-1",
                    "content": "child transcript",
                },
            )

        regular_client = socketio_lib.AsyncSimpleClient()
        await regular_client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await regular_client.emit("agent:join", {"session_id": "parent-session"})
        joined_parent = await asyncio.wait_for(regular_client.receive(), timeout=2.0)
        assert joined_parent[0] == "agent:joined"
        assert joined_parent[1] == {"session_id": "parent-session"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(regular_client.receive(), timeout=0.3)

        await regular_client.disconnect()

        parent_client = socketio_lib.AsyncSimpleClient()
        await parent_client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await parent_client.emit(
            "agent:join_subagents",
            {"session_id": "parent-session"},
        )
        joined_event = await asyncio.wait_for(parent_client.receive(), timeout=2.0)
        assert joined_event[0] == "agent:joined_subagents"
        assert joined_event[1] == {"session_id": "parent-session"}

        replayed_status = await asyncio.wait_for(parent_client.receive(), timeout=2.0)
        assert replayed_status[0] == "agent:subagent_status"
        assert replayed_status[1] == {
            "parent_session_id": "parent-session",
            "child_run_id": "child-run-1",
            "child_thread_id": "child-thread-1",
            "agent_key": "writer",
            "status": "running",
            "queued_messages": 1,
            "is_active": True,
        }

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(parent_client.receive(), timeout=0.3)

        await emit(
            "agent:token",
            {
                "session_id": "child-thread-1",
                "run_id": "child-run-1",
                "content": "live child transcript",
            },
            room=agent_subagent_session_room("child-thread-1"),
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(parent_client.receive(), timeout=0.3)

        await emit(
            "agent:subagent_status",
            {
                "parent_session_id": "parent-session",
                "child_run_id": "child-run-1",
                "child_thread_id": "child-thread-1",
                "agent_key": "writer",
                "status": "completed",
                "queued_messages": 0,
                "is_active": True,
            },
            room=agent_subagents_room("parent-session"),
        )
        live_status = await asyncio.wait_for(parent_client.receive(), timeout=2.0)
        assert live_status[0] == "agent:subagent_status"
        assert live_status[1]["status"] == "completed"

        await parent_client.disconnect()

    async def test_join_agent_session_emits_task_usage_snapshot_then_deltas(
        self,
        server,
        socket_db_factory,
    ):
        await _seed_project(
            socket_db_factory,
            project_id="project-usage",
            chapter_id="chapter-usage",
        )
        async with socket_db_factory() as session:
            session.add(Task(
                id="task-usage",
                project_id="project-usage",
                title="Task",
                mode="agent",
                agent_session_id="parent-session-usage",
                token_input=100,
                token_output=40,
                token_cache=8,
                context_input_tokens=12,
            ))
            await session.commit()

        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit("agent:join", {"session_id": "parent-session-usage"})
        joined_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert joined_event[0] == "agent:joined"
        assert joined_event[1] == {"session_id": "parent-session-usage"}

        snapshot_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert snapshot_event[0] == "agent:task_usage_snapshot"
        assert snapshot_event[1] == {
            "session_id": "parent-session-usage",
            "task_id": "task-usage",
            "token_input": 100,
            "token_output": 40,
            "token_cache": 8,
        }

        await emit(
            "agent:task_usage_delta",
            {
                "session_id": "parent-session-usage",
                "task_id": "task-usage",
                "token_input": 10,
                "token_output": 4,
                "token_cache": 1,
            },
            room=agent_subagent_session_room("child-thread-ignored"),
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.receive(), timeout=0.3)

        await emit(
            "agent:task_usage_delta",
            {
                "session_id": "parent-session-usage",
                "task_id": "task-usage",
                "token_input": 10,
                "token_output": 4,
                "token_cache": 1,
            },
            room="agent_session:parent-session-usage",
        )
        delta_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert delta_event[0] == "agent:task_usage_delta"
        assert delta_event[1] == {
            "session_id": "parent-session-usage",
            "task_id": "task-usage",
            "token_input": 10,
            "token_output": 4,
            "token_cache": 1,
        }

        await client.disconnect()

    async def test_join_subagent_replays_and_receives_child_transcript(
        self,
        server,
    ):
        buffer = get_agent_event_replay_buffer()
        async with buffer.session_lock("child-thread-2"):
            buffer.record_unlocked(
                "agent:token",
                {
                    "session_id": "child-thread-2",
                    "run_id": "child-run-2",
                    "content": "buffered child transcript",
                },
            )

        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit(
            "agent:join_subagent",
            {"child_thread_id": "child-thread-2"},
        )
        joined_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert joined_event[0] == "agent:joined_subagent"
        assert joined_event[1] == {"child_thread_id": "child-thread-2"}

        replayed_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert replayed_event[0] == "agent:token"
        assert replayed_event[1] == {
            "session_id": "child-thread-2",
            "run_id": "child-run-2",
            "content": "buffered child transcript",
        }

        await emit(
            "agent:token",
            {
                "session_id": "child-thread-2",
                "run_id": "child-run-2",
                "content": "live child transcript",
            },
            room=agent_subagent_session_room("child-thread-2"),
        )
        live_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert live_event[0] == "agent:token"
        assert live_event[1] == {
            "session_id": "child-thread-2",
            "run_id": "child-run-2",
            "content": "live child transcript",
        }

        await client.disconnect()

    async def test_join_background_project_room_receives_snapshot_and_room_event(
        self, server, socket_db_factory
    ):
        await _seed_project(socket_db_factory, project_id="p1", chapter_id="c1")
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit("background:join", {"project_id": "p1"})
        snapshot = await _expect_background_joined_and_snapshot(client, "p1")
        assert snapshot["summary"]["statuses"] == [
            {
                "chapter_id": "c1",
                "volume_id": "p1-volume-1",
                "status": "not_generated",
                "is_stale": False,
                "summary_id": None,
                "updated_at": None,
            }
        ]
        missing = snapshot["summary"]["maintenance"]["missing_or_failed_chapter_summaries"]
        assert [item["chapter_id"] for item in missing] == ["c1"]

        await emit(
            "background:task",
            {"project_id": "p1", "status": "running"},
            room=background_project_room("p1"),
        )
        event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert event[0] == "background:task"
        assert event[1] == {"project_id": "p1", "status": "running"}

        await client.disconnect()

    async def test_background_leave_removes_client_from_room(self, server):
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit("background:join", {"project_id": "p1"})
        await _expect_background_joined_and_snapshot(client, "p1")

        await client.emit("background:leave", {"project_id": "p1"})
        left_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert left_event[0] == "background:left"
        assert left_event[1] == {"project_id": "p1"}

        await emit(
            "background:task",
            {"project_id": "p1", "status": "after-leave"},
            room=background_project_room("p1"),
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.receive(), timeout=0.3)

        await client.disconnect()

    @pytest.mark.parametrize("payload", [{}, {"project_id": ""}])
    async def test_invalid_background_join_project_id_emits_error(self, server, payload):
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client.emit("background:join", payload)
        error_event = await asyncio.wait_for(client.receive(), timeout=2.0)
        assert error_event[0] == "background:error"
        assert error_event[1] == {
            "type": "invalid_project",
            "reason": "project_id is required",
        }

        await client.disconnect()

    async def test_background_project_rooms_and_snapshots_are_isolated(self, server, socket_db_factory):
        await _seed_project(socket_db_factory, project_id="p1", chapter_id="c1")
        await _seed_project(socket_db_factory, project_id="p2", chapter_id="c2", status="ready")

        client_a = socketio_lib.AsyncSimpleClient()
        client_b = socketio_lib.AsyncSimpleClient()
        await client_a.connect(server, socketio_path="/socket.io")
        await client_b.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        await client_a.emit("background:join", {"project_id": "p1"})
        snapshot_a = await _expect_background_joined_and_snapshot(client_a, "p1")

        await client_b.emit("background:join", {"project_id": "p2"})
        snapshot_b = await _expect_background_joined_and_snapshot(client_b, "p2")

        assert [item["chapter_id"] for item in snapshot_a["summary"]["statuses"]] == ["c1"]
        assert [item["chapter_id"] for item in snapshot_b["summary"]["statuses"]] == ["c2"]
        assert snapshot_b["summary"]["statuses"][0]["status"] == "ready"

        await emit(
            "background:task",
            {"project_id": "p1", "status": "done"},
            room=background_project_room("p1"),
        )
        event_a = await asyncio.wait_for(client_a.receive(), timeout=2.0)
        assert event_a[0] == "background:task"
        assert event_a[1] == {"project_id": "p1", "status": "done"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client_b.receive(), timeout=0.3)

        await client_a.disconnect()
        await client_b.disconnect()

    async def test_heartbeat_updates_state(self, server):
        client = socketio_lib.AsyncSimpleClient()
        await client.connect(server, socketio_path="/socket.io")
        await asyncio.sleep(0.1)

        state = get_connection_state()
        old_seen = state.last_seen_at
        await asyncio.sleep(0.05)

        await client.emit("heartbeat", {})
        await asyncio.sleep(0.1)
        assert state.last_seen_at > old_seen

        await client.disconnect()
