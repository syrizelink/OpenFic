"""MessagePersister 测试 — 正常路径。"""

from datetime import UTC, datetime

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.messages.tool import invalid_tool_call
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence import persister as persister_module
from app.agent_runtime.persistence.persister import MessagePersister


def _stream_event(event: str, **data) -> dict:
    return {"event": event, **data}


@pytest.mark.asyncio
async def test_persister_normal_chat_model_stream(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.handle({
        "event": "on_chain_start",
        "name": "writer",
        "tags": ["agent_node"],
        "data": {},
    })
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle({
        "event": "on_chat_model_stream",
        "data": {"chunk": AIMessageChunk(content="hello ")},
    })
    await p.handle({
        "event": "on_chat_model_stream",
        "data": {"chunk": AIMessageChunk(content="world")},
    })
    await p.handle({
        "event": "on_chat_model_end",
        "data": {"output": AIMessageChunk(content="hello world")},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    msg = items[0]
    assert msg.role == "assistant"
    assert msg.status == "complete"
    assert msg.content == "hello world"
    assert msg.agent_id == "writer"


@pytest.mark.asyncio
async def test_persister_persists_non_streaming_chat_model_end_output(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_non_streaming"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.handle({
        "event": "on_chain_start",
        "name": "composer",
        "tags": ["agent_node"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_start",
        "run_id": "non-stream-run",
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_end",
        "run_id": "non-stream-run",
        "data": {"output": AIMessage(content="final non-stream answer")},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    assert items[0].role == "assistant"
    assert items[0].status == "complete"
    assert items[0].content == "final non-stream answer"
    assert items[0].agent_id == "composer"


@pytest.mark.asyncio
async def test_persister_ignores_subagent_child_events(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_parent"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.handle({"event": "on_chat_model_start", "tags": ["subagent_child"], "data": {}})
    await p.handle({
        "event": "on_chat_model_stream",
        "tags": ["subagent_child"],
        "data": {"chunk": AIMessageChunk(content="hidden child output")},
    })
    await p.handle({
        "event": "on_chat_model_end",
        "tags": ["subagent_child"],
        "data": {"output": AIMessageChunk(content="hidden child output")},
    })
    await p.handle({
        "event": "on_tool_end",
        "name": "read_chapter",
        "run_id": "child-tool-run",
        "tags": ["subagent_child"],
        "data": {"output": "hidden child tool result"},
    })

    items = await repo.list_by_session(db_session, sid)
    assert items == []


@pytest.mark.asyncio
async def test_persister_persists_subagent_child_events_when_opted_in(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "child-session"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
        allow_subagent_child_events=True,
    )

    await p.handle({
        "event": "on_chain_start",
        "name": "writer",
        "tags": ["agent_node", "subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_start",
        "run_id": "child-run-1",
        "tags": ["subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_stream",
        "run_id": "child-run-1",
        "tags": ["subagent_child"],
        "data": {"chunk": AIMessageChunk(content="visible child output")},
    })
    await p.handle({
        "event": "on_chat_model_end",
        "run_id": "child-run-1",
        "tags": ["subagent_child"],
        "data": {"output": AIMessageChunk(content="visible child output")},
    })
    await p.handle({
        "event": "on_tool_start",
        "name": "read_chapter",
        "run_id": "child-tool-run",
        "tags": ["subagent_child"],
        "data": {"input": {"order": 1}},
        "metadata": {"tool_call_id": "call-child-tool"},
    })
    await p.handle({
        "event": "on_tool_end",
        "name": "read_chapter",
        "run_id": "child-tool-run",
        "tags": ["subagent_child"],
        "data": {"output": "visible child tool result"},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 2
    assert items[0].role == "assistant"
    assert items[0].status == "complete"
    assert items[0].content == "visible child output"
    assert items[0].agent_id == "writer"
    assert items[1].role == "tool"
    assert items[1].status == "complete"
    assert items[1].tool_call_id == "call-child-tool"
    assert items[1].tool_name == "read_chapter"
    assert items[1].content == "visible child tool result"


@pytest.mark.asyncio
async def test_persister_persists_subagent_tool_error_when_approval_interrupts(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "child-session-tool-error"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
        allow_subagent_child_events=True,
    )

    await p.handle({
        "event": "on_chain_start",
        "name": "composer",
        "tags": ["agent_node", "subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_start",
        "run_id": "child-run-approval",
        "tags": ["subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_end",
        "run_id": "child-run-approval",
        "tags": ["subagent_child"],
        "data": {
            "output": AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-write-plan",
                        "name": "write_plan",
                        "args": {"value": "plan child beats"},
                    }
                ],
            ),
        },
    })
    await p.handle({
        "event": "on_tool_start",
        "name": "write_plan",
        "run_id": "child-tool-approval",
        "tags": ["subagent_child"],
        "data": {"input": {"value": "plan child beats"}},
        "metadata": {"tool_call_id": "call-write-plan"},
    })
    await p.handle({
        "event": "on_tool_error",
        "name": "write_plan",
        "run_id": "child-tool-approval",
        "tags": ["subagent_child"],
        "data": {
            "input": {"value": "plan child beats"},
            "error": RuntimeError("approval required"),
        },
        "metadata": {"tool_call_id": "call-write-plan"},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 2
    assert items[0].role == "assistant"
    tool_calls = items[0].tool_calls
    assert tool_calls is not None
    assert tool_calls[0]["id"] == "call-write-plan"
    assert tool_calls[0]["name"] == "write_plan"
    assert tool_calls[0]["args"] == {"value": "plan child beats"}
    assert items[1].role == "tool"
    assert items[1].status == "complete"
    assert items[1].tool_call_id == "call-write-plan"
    assert items[1].tool_name == "write_plan"
    assert "\"reason\": \"approval_preview\"" in items[1].content


@pytest.mark.asyncio
async def test_persister_persists_reasoning_duration_on_chat_model_end(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_reasoning_duration"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle({
        "event": "on_chat_model_stream",
        "data": {
            "chunk": AIMessageChunk(
                content="",
                additional_kwargs={"reasoning_content": "先分析需求"},
            ),
        },
    })
    await p.handle({
        "event": "on_chat_model_end",
        "data": {"output": AIMessageChunk(content="")},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    msg = items[0]
    assert msg.reasoning == "先分析需求"
    assert msg.reasoning_duration_ms is not None
    assert msg.reasoning_duration_ms == 0


@pytest.mark.asyncio
async def test_persister_stops_reasoning_duration_at_last_reasoning_chunk(
    db_session: AsyncSession, db_session_factory, sample_task, monkeypatch
):
    class FrozenDateTime(datetime):
        current = datetime(2026, 1, 1, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.current if tz is not None else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(persister_module, "datetime", FrozenDateTime)

    sid = "session_reasoning_stops_at_last_chunk"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.handle({"event": "on_chat_model_start", "run_id": "run-1", "data": {}})

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
    await p.handle({
        "event": "on_chat_model_stream",
        "run_id": "run-1",
        "data": {
            "chunk": AIMessageChunk(
                content="",
                additional_kwargs={"reasoning_content": "先分析"},
            ),
        },
    })

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 3, tzinfo=UTC)
    await p.handle({
        "event": "on_chat_model_stream",
        "run_id": "run-1",
        "data": {
            "chunk": AIMessageChunk(
                content="",
                additional_kwargs={"reasoning_content": "再推演"},
            ),
        },
    })

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)
    await p.handle({
        "event": "on_chat_model_stream",
        "run_id": "run-1",
        "data": {"chunk": AIMessageChunk(content="最终结论")},
    })

    FrozenDateTime.current = datetime(2026, 1, 1, 0, 0, 7, tzinfo=UTC)
    await p.handle({
        "event": "on_chat_model_end",
        "run_id": "run-1",
        "data": {"output": AIMessageChunk(content="最终结论")},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    msg = items[0]
    assert msg.reasoning == "先分析再推演"
    assert msg.reasoning_duration_ms == 2000


@pytest.mark.asyncio
async def test_persister_tool_start_end_writes_tool_complete(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.handle({
        "event": "on_tool_start",
        "name": "read_chapter",
        "run_id": "run-1",
        "data": {"input": {"order": 1}},
        "metadata": {"tool_call_id": "c1"},
    })
    await p.handle({
        "event": "on_tool_end",
        "name": "read_chapter",
        "run_id": "run-1",
        "data": {"output": "chapter body"},
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    msg = items[0]
    assert msg.role == "tool"
    assert msg.status == "complete"
    assert msg.tool_call_id == "c1"
    assert msg.tool_name == "read_chapter"
    assert msg.content == "chapter body"


@pytest.mark.asyncio
async def test_persister_assistant_with_tool_calls(
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
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{"index": 0, "id": "c1", "name": "read_chapter", "args": ""}],
    )
    await p.handle({"event": "on_chat_model_stream", "data": {"chunk": chunk}})
    chunk2 = AIMessageChunk(
        content="",
        tool_call_chunks=[{"index": 0, "id": None, "name": None, "args": '{"order":1}'}],
    )
    await p.handle({"event": "on_chat_model_stream", "data": {"chunk": chunk2}})
    await p.handle({"event": "on_chat_model_end", "data": {}})

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    assert items[0].role == "assistant"
    assert items[0].status == "complete"
    assert items[0].tool_calls == [
        {"id": "c1", "name": "read_chapter", "args": {"order": 1}}
    ]


@pytest.mark.asyncio
async def test_persister_recovers_malformed_write_plan_todos_for_reload(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "child-session-invalid-write-plan"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
        allow_subagent_child_events=True,
    )
    malformed_args = (
        '{"todos":[{"content":"line1\nline2","status":"pending","priority":"high"},'
        '{"content":"done","status":"completed","priority":"low"}]}'
    )

    await p.handle({
        "event": "on_chain_start",
        "name": "composer",
        "tags": ["agent_node", "subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_start",
        "run_id": "child-run-invalid-tool-call",
        "tags": ["subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_stream",
        "run_id": "child-run-invalid-tool-call",
        "tags": ["subagent_child"],
        "data": {
            "chunk": AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "index": 0,
                        "id": "call-write-plan",
                        "name": "write_plan",
                        "args": malformed_args,
                    }
                ],
            )
        },
    })
    await p.handle({
        "event": "on_chat_model_end",
        "run_id": "child-run-invalid-tool-call",
        "tags": ["subagent_child"],
        "data": {
            "output": AIMessage(
                content="",
                invalid_tool_calls=[
                    invalid_tool_call(
                        id="call-write-plan",
                        name="write_plan",
                        args=malformed_args,
                        error="invalid json in todos array",
                    )
                ],
            )
        },
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 1
    assert items[0].role == "assistant"
    assert items[0].tool_calls == [
        {
            "id": "call-write-plan",
            "name": "write_plan",
            "args": {
                "todos": [
                    {"content": "line1\nline2", "status": "pending", "priority": "high"},
                    {"content": "done", "status": "completed", "priority": "low"},
                ],
            },
        }
    ]


@pytest.mark.asyncio
async def test_persister_persists_unrecoverable_invalid_tool_call_with_synthesized_id(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "child-session-invalid-write-plan-no-id"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
        allow_subagent_child_events=True,
    )

    await p.handle({
        "event": "on_chain_start",
        "name": "composer",
        "tags": ["agent_node", "subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_start",
        "run_id": "child-run-invalid-tool-call-no-id",
        "tags": ["subagent_child"],
        "data": {},
    })
    await p.handle({
        "event": "on_chat_model_stream",
        "run_id": "child-run-invalid-tool-call-no-id",
        "tags": ["subagent_child"],
        "data": {
            "chunk": AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "index": 0,
                        "id": None,
                        "name": "write_plan",
                        "args": "<<<<",
                    }
                ],
            )
        },
    })
    await p.handle({
        "event": "on_chat_model_end",
        "run_id": "child-run-invalid-tool-call-no-id",
        "tags": ["subagent_child"],
        "data": {
            "output": AIMessage(
                content="",
                invalid_tool_calls=[
                    {
                        "name": "write_plan",
                        "args": "<<<<",
                        "error": "invalid json",
                        "type": "invalid_tool_call",
                    }
                ],
            )
        },
    })

    items = await repo.list_by_session(db_session, sid)
    assert len(items) == 2
    assistant = items[0]
    tool = items[1]
    assert assistant.role == "assistant"
    assert assistant.tool_calls is not None
    assert len(assistant.tool_calls) == 1
    synthesized_id = assistant.tool_calls[0]["id"]
    assert isinstance(synthesized_id, str) and synthesized_id
    assert assistant.tool_calls[0]["name"] == "write_plan"
    assert tool.role == "tool"
    assert tool.tool_call_id == synthesized_id
    assert tool.tool_name == "write_plan"
    assert '"reason": "malformed_tool_call"' in tool.content


@pytest.mark.asyncio
async def test_persister_mark_user_sent(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    pending = await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user", content="hi", status="pending",
    )
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )
    await p.mark_user_sent(pending.id)
    items = await repo.list_by_session(db_session, sid)
    assert items[0].status == "sent"


@pytest.mark.asyncio
async def test_persister_persists_node_events_as_hidden_system_messages(
    db_session: AsyncSession, db_session_factory, sample_task
):
    sid = "session_a"
    p = MessagePersister(
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=db_session_factory,
    )

    await p.persist_node_event({
        "session_id": sid,
        "node": "composer",
        "phase": "start",
        "status": "running",
        "current_node": "composer",
        "previous_node": "explorer",
    })
    await p.persist_node_event({
        "session_id": sid,
        "node": "composer",
        "phase": "end",
        "status": "completed",
        "current_node": None,
        "previous_node": "explorer",
    })

    items = await repo.list_by_session(db_session, sid)
    assert [item.role for item in items] == ["system", "system"]
    assert [item.agent_id for item in items] == ["composer", "composer"]
    assert [item.message_type for item in items] == ["node_start", "node_end"]
    assert [item.display_channel for item in items] == ["hidden", "hidden"]
    assert [item.status for item in items] == ["complete", "complete"]
    assert items[0].metadata == {
        "kind": "agent_node",
        "event_type": "node_start",
        "node": "composer",
        "phase": "start",
        "node_status": "running",
        "current_node": "composer",
        "previous_node": "explorer",
    }
    assert items[1].metadata["event_type"] == "node_end"
    assert items[1].metadata["node_status"] == "completed"
