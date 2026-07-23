"""MessagePersister.finalize 测试 — 中断场景。"""

import json
from datetime import UTC, datetime

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence import persister as persister_module
from app.agent_runtime.persistence.persister import MessagePersister


@pytest.mark.asyncio
async def test_finalize_writes_partial_assistant_with_resolvable_tool_call(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle(
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": AIMessageChunk(content="half-")},
        }
    )
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[
            {"index": 0, "id": "c1", "name": "read_chapter", "args": '{"order":1}'}
        ],
    )
    await p.handle({"event": "on_chat_model_stream", "data": {"chunk": chunk}})

    await p.finalize(reason="cancelled")

    items = await repo.list_by_session(db_session, sid)
    roles = [(m.role, m.status) for m in items]
    assert ("assistant", "partial") in roles
    assert ("tool", "aborted") in roles
    assistant = next(m for m in items if m.role == "assistant")
    assert assistant.content == "half-"
    assert assistant.tool_calls == [
        {"id": "c1", "name": "read_chapter", "args": {"order": 1}}
    ]
    tool = next(m for m in items if m.role == "tool")
    assert tool.tool_call_id == "c1"
    assert tool.tool_name == "read_chapter"
    assert "中断" in tool.content


@pytest.mark.asyncio
async def test_finalize_drops_unresolvable_tool_calls(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle(
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": AIMessageChunk(content="thinking ")},
        }
    )
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{"index": 0, "id": "c1", "name": None, "args": ""}],
    )
    await p.handle({"event": "on_chat_model_stream", "data": {"chunk": chunk}})

    await p.finalize(reason="cancelled")

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    assert items[0].role == "assistant"
    assert items[0].status == "partial"
    assert items[0].content == "thinking "
    assert items[0].tool_calls is None


@pytest.mark.asyncio
async def test_finalize_persists_reasoning_duration_for_cancelled_partial_message(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_reasoning_cancelled"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle(
        {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": AIMessageChunk(
                    content="",
                    additional_kwargs={"reasoning_content": "先分析到一半"},
                ),
            },
        }
    )

    await p.finalize(reason="cancelled")

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    msg = items[0]
    assert msg.role == "assistant"
    assert msg.status == "partial"
    assert msg.reasoning == "先分析到一半"
    assert msg.reasoning_duration_ms is not None
    assert msg.reasoning_duration_ms == 0


@pytest.mark.asyncio
async def test_finalize_stops_reasoning_duration_at_last_reasoning_chunk(
    db_session: AsyncSession, db_session_factory, sample_task, monkeypatch
):
    class FrozenDateTime(datetime):
        current = datetime(2026, 1, 1, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.current if tz is not None else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(persister_module, "datetime", FrozenDateTime)

    sid = "session_reasoning_cancelled_stops_at_last_chunk"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.handle({"event": "on_chat_model_start", "run_id": "run-1", "data": {}})

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
    await p.handle(
        {
            "event": "on_chat_model_stream",
            "run_id": "run-1",
            "data": {
                "chunk": AIMessageChunk(
                    content="",
                    additional_kwargs={"reasoning_content": "先分析"},
                ),
            },
        }
    )

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 3, tzinfo=UTC)
    await p.handle(
        {
            "event": "on_chat_model_stream",
            "run_id": "run-1",
            "data": {
                "chunk": AIMessageChunk(
                    content="",
                    additional_kwargs={"reasoning_content": "再推演"},
                ),
            },
        }
    )

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)
    await p.handle(
        {
            "event": "on_chat_model_stream",
            "run_id": "run-1",
            "data": {"chunk": AIMessageChunk(content="尾声")},
        }
    )

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 7, tzinfo=UTC)
    await p.finalize(reason="cancelled")

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    msg = items[0]
    assert msg.reasoning == "先分析再推演"
    assert msg.reasoning_duration_ms == 2000


@pytest.mark.asyncio
async def test_finalize_writes_aborted_for_tool_started_not_ended(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.handle(
        {
            "event": "on_tool_start",
            "name": "write_chapter",
            "run_id": "tool-1",
            "data": {"input": {}},
            "metadata": {"tool_call_id": "tc1"},
        }
    )
    await p.finalize(reason="cancelled")
    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    assert items[0].role == "tool"
    assert items[0].status == "aborted"
    assert items[0].tool_call_id == "tc1"
    assert items[0].tool_name == "write_chapter"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "tool_call_id", "tool_args"),
    [
        (
            "dispatch_subagent",
            "call-dispatch",
            {"agent_type": "writer", "prompt": "write scene"},
        ),
        (
            "notify_subagent",
            "call-notify",
            {"dispatch_id": "dispatch-cancelled", "prompt": "continue scene"},
        ),
    ],
)
async def test_finalize_preserves_cancelled_subagent_tool_identity_in_history(
    db_session: AsyncSession,
    db_session_factory,
    sample_task,
    tool_name: str,
    tool_call_id: str,
    tool_args: dict[str, str],
):
    session_id = "parent-session"
    await repo.insert_message(
        db_session,
        session_id=session_id,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        status="complete",
        content="",
        tool_calls=[
            {
                "id": "call-dispatch",
                "name": "dispatch_subagent",
                "args": {"agent_type": "writer", "prompt": "write scene"},
            },
            {
                "id": "call-notify",
                "name": "notify_subagent",
                "args": {
                    "dispatch_id": "dispatch-cancelled",
                    "prompt": "continue scene",
                },
            },
        ],
    )
    await create_child_run(
        db_session,
        parent_session_id=session_id,
        parent_task_id=sample_task.id,
        parent_thread_id=session_id,
        child_thread_id="parent-session:child:dispatch-cancelled",
        agent_key="writer",
        dispatch_id="dispatch-cancelled",
        tool_call_id="call-dispatch",
        request={"task": "write scene"},
        metadata={"agent_number": "#1001"},
    )
    persister = MessagePersister(
        session_id=session_id,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await persister.handle(
        {
            "event": "on_tool_start",
            "name": tool_name,
            "run_id": f"tool-{tool_name}",
            "data": {"input": tool_args},
            "metadata": {"tool_call_id": tool_call_id},
        }
    )

    await persister.finalize(reason="cancelled")

    messages = await load_history(db_session, session_id)

    assert isinstance(messages[0], AIMessage)
    assert isinstance(messages[1], ToolMessage)
    assert json.loads(messages[1].content) == {
        "dispatch_id": "dispatch-cancelled",
        "agent_key": "writer",
        "agent_number": "#1001",
        "error": "subagent 会话已被用户中断，要通知其继续工作请使用 notify_subagent",
    }


@pytest.mark.asyncio
async def test_finalize_skips_completely_empty_buffer(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.finalize(reason="cancelled")
    items = await repo.list_by_session(db_session, sid)
    assert items == []


@pytest.mark.asyncio
async def test_finalize_done_path_no_open_buffers(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.finalize(reason="done")
    items = await repo.list_by_session(db_session, sid)
    assert items == []
