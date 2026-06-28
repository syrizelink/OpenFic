"""SessionRunner 与持久化层的集成测试。"""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.child_runs import (
    claim_next_child_run_request,
    complete_child_run_request,
)
from app.agent_runtime.persistence.model import AgentChildRun
from app.agent_runtime.graph.orchestrator.graph import build_orchestrator_graph
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.runner.session_runner import SessionRunner
from app.storage.database import _set_sqlite_pragma  # noqa: F401  ensure module ready
from tests.model_registry import register_sqlmodel_models


def _model_config() -> dict:
    return {"max_context_tokens": 8000}


def test_session_runner_requires_task_id():
    with pytest.raises(TypeError):
        SessionRunner(  # type: ignore[call-arg]
            session_id="s",
            model_config=_model_config(),
        )


def test_session_runner_accepts_task_id():
    runner = SessionRunner(
        session_id="s",
        task_id="task_x",
        model_config=_model_config(),
        project_id="proj_x",
    )
    assert runner.task_id == "task_x"


@pytest.fixture(autouse=True)
def stub_agent_audit_queue(monkeypatch):
    async def fake_enqueue_audit_log(_audit_log):
        return None

    async def fake_next_call_sequence(_session_id):
        return 1

    monkeypatch.setattr(
        "app.agent_runtime.audit.collector.enqueue_audit_log",
        fake_enqueue_audit_log,
    )
    monkeypatch.setattr(
        "app.agent_runtime.audit.collector.next_call_sequence",
        fake_next_call_sequence,
    )


def test_build_runtime_config_passes_compaction_sinks_to_graph():
    runner = SessionRunner(
        session_id="s",
        task_id="task_x",
        model_config=_model_config(),
        project_id="proj_x",
    )

    config = runner._build_runtime_config(
        runtime_session=object(),  # type: ignore[arg-type]
        runtime_context={},
        audit_collector=object(),  # type: ignore[arg-type]
    )

    configurable = config["configurable"]
    agent_event_sink = configurable["agent_event_sink"]
    compaction_usage_sink = configurable["compaction_usage_sink"]
    assert callable(agent_event_sink)
    assert callable(compaction_usage_sink)
    assert agent_event_sink.__self__ is runner
    assert agent_event_sink.__func__ is SessionRunner._emit_agent_event
    assert compaction_usage_sink.__self__ is runner
    assert (
        compaction_usage_sink.__func__
        is SessionRunner._emit_persisted_task_usage_events
    )


@pytest_asyncio.fixture
async def isolated_db(monkeypatch):
    """把全局 _async_session_factory / _engine 替换成内存库，并建表。"""
    import app.storage.database as db_mod

    register_sqlmodel_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    monkeypatch.setattr(db_mod, "_engine", engine, raising=False)
    monkeypatch.setattr(db_mod, "_async_session_factory", factory, raising=False)

    async with factory() as session:
        from app.storage.models.chapter import Chapter
        from app.storage.models.project import Project
        from app.storage.models.task import Task
        from app.storage.models.volume import Volume

        session.add(Project(id="proj_x", title="t"))
        session.add(
            Volume(
                id="vol_x",
                project_id="proj_x",
                title="第一卷",
                order=1,
                chapter_count=1,
            )
        )
        session.add(
            Chapter(
                id="chap_x",
                project_id="proj_x",
                volume_id="vol_x",
                title="c",
                order=1,
            )
        )
        session.add(Task(
            id="task_x", project_id="proj_x",
            title="t", mode="agent", agent_session_id="session_x",
        ))
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_runner_clears_pending_on_run_start(isolated_db):
    """run 启动时调 delete_pending_by_session 清掉残留 pending。"""
    factory = isolated_db
    async with factory() as s:
        await repo.insert_message(
            s, session_id="s_x", task_id="task_x", project_id="proj_x",
            role="user", content="orphan-pending", status="pending",
        )

    runner = SessionRunner(
        session_id="s_x",
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )
    await runner._prepare_run_persistence()

    async with factory() as s:
        items = await repo.list_by_session(s, "s_x")
    assert items == []


@pytest.mark.asyncio
async def test_drain_inject_queue_marks_user_sent(isolated_db):
    factory = isolated_db
    sid = "s_x"
    async with factory() as s:
        m = await repo.insert_message(
            s, session_id=sid, task_id="task_x", project_id="proj_x",
            role="user", content="hi", status="pending",
        )

    runner = SessionRunner(
        session_id=sid, task_id="task_x",
        model_config={"max_context_tokens": 8000}, project_id="proj_x",
    )
    runner._persister = runner._make_persister()
    await runner._inject_queue.put((m.id, "user", "hi"))

    drained = await runner._drain_inject_queue()
    assert len(drained) == 1
    role, content, _msg_id = drained[0]
    assert role == "user"
    assert content == "hi"

    async with factory() as s:
        items = await repo.list_by_session(s, sid)
    assert items[0].status == "sent"


@pytest.mark.asyncio
async def test_queue_pending_user_message_enqueues_without_persisting_until_consumed(
    isolated_db,
    monkeypatch,
):
    factory = isolated_db
    sid = "s_x"
    emitted: list[tuple[str, dict]] = []
    raw_follow_up = 'follow-up<of-mention kind="volume" volume_id="vol_x" label="旧卷" />'
    compiled_follow_up = "follow-up\n> 引用卷：第一卷"

    async def capture_emit(name, payload=None, *_args, **_kwargs):
        emitted.append((name, payload or {}))
        return None

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", capture_emit)

    runner = SessionRunner(
        session_id=sid,
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )

    pending = await runner.queue_pending_user_message(raw_follow_up)

    assert pending["content"] == compiled_follow_up
    assert isinstance(pending["created_at"], str) and pending["created_at"]

    queued = runner._inject_queue.get_nowait()
    queued_message_id, role, content = queued
    assert pending["message_id"] == queued_message_id
    assert isinstance(queued_message_id, str) and queued_message_id
    assert role == "user"
    assert content == compiled_follow_up
    assert queued_message_id in runner._queued_user_messages

    async with factory() as s:
        items = await repo.list_by_session(s, sid)
    assert items == []
    assert any(
        name == "agent:pending_message"
        and payload.get("message_id") == queued_message_id
        and payload.get("action") == "queued"
        for name, payload in emitted
    )


@pytest.mark.asyncio
async def test_cancel_pending_user_message_emits_cancel_event_and_skips_injection(
    isolated_db,
    monkeypatch,
):
    factory = isolated_db
    sid = "s_x"
    emitted: list[tuple[str, dict]] = []
    raw_follow_up = 'follow-up<of-mention kind="volume" volume_id="vol_x" label="旧卷" />'
    compiled_follow_up = "follow-up\n> 引用卷：第一卷"

    async def capture_emit(name, payload=None, *_args, **_kwargs):
        emitted.append((name, payload or {}))
        return None

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", capture_emit)

    runner = SessionRunner(
        session_id=sid,
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )

    pending = await runner.queue_pending_user_message(raw_follow_up)
    restored = await runner.cancel_pending_user_message(pending["message_id"])

    assert restored["message_id"] == pending["message_id"]
    assert restored["content"] == compiled_follow_up
    assert pending["message_id"] not in runner._queued_user_messages

    runner._persister = runner._make_persister()
    drained = await runner._drain_inject_queue()
    assert drained == []

    async with factory() as s:
        items = await repo.list_by_session(s, sid)
    assert items == []
    assert any(
        name == "agent:pending_message"
        and payload.get("message_id") == pending["message_id"]
        and payload.get("action") == "cancelled"
        for name, payload in emitted
    )


@pytest.mark.asyncio
async def test_drain_inject_queue_emits_consumed_and_user_text_for_pending_message(
    isolated_db,
    monkeypatch,
):
    factory = isolated_db
    sid = "s_x"
    emitted: list[tuple[str, dict]] = []
    raw_follow_up = 'follow-up<of-mention kind="volume" volume_id="vol_x" label="旧卷" />'
    compiled_follow_up = "follow-up\n> 引用卷：第一卷"

    async def capture_emit(name, payload=None, *_args, **_kwargs):
        emitted.append((name, payload or {}))
        return None

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", capture_emit)

    runner = SessionRunner(
        session_id=sid,
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )

    pending = await runner.queue_pending_user_message(raw_follow_up)
    runner._persister = runner._make_persister()

    drained = await runner._drain_inject_queue()
    assert drained == [("user", compiled_follow_up, pending["message_id"])]

    async with factory() as s:
        items = await repo.list_by_session(s, sid)

    assert [(item.role, item.content, item.status) for item in items] == [
        ("user", compiled_follow_up, "sent"),
    ]
    queued_index = next(
        index
        for index, (name, payload) in enumerate(emitted)
        if name == "agent:pending_message"
        and payload.get("message_id") == pending["message_id"]
        and payload.get("action") == "queued"
    )
    consumed_index = next(
        index
        for index, (name, payload) in enumerate(emitted)
        if name == "agent:pending_message"
        and payload.get("message_id") == pending["message_id"]
        and payload.get("action") == "consumed"
    )
    text_index = next(
        index
        for index, (name, payload) in enumerate(emitted)
        if name == "agent:text"
        and payload.get("message_id") == pending["message_id"]
    )
    assert queued_index < consumed_index < text_index


@pytest.mark.asyncio
async def test_run_consumes_queued_follow_up_before_turn_finishes(
    isolated_db,
    monkeypatch,
):
    factory = isolated_db
    raw_follow_up = 'follow-up<of-mention kind="volume" volume_id="vol_x" label="旧卷" />'
    compiled_follow_up = "follow-up\n> 引用卷：第一卷"

    class _FakeModel:
        def bind_tools(self, _tools):
            return self

    async def noop_emit(*_args, **_kwargs):
        return None

    async def noop_node_event(*_args, **_kwargs):
        return None

    async def fake_build_context(**_kwargs):
        return [HumanMessage(content="turn:1")]

    runner = SessionRunner(
        session_id="session_x",
        task_id="task_x",
        model_config={
            "provider_type": "openai-compatible",
            "base_url": "https://example.test",
            "api_key": "test-key",
            "model_id": "test-model",
            "max_context_tokens": 8000,
        },
        project_id="proj_x",
    )
    model_call_count = {"value": 0}

    async def fake_invoke_model(_model, _messages):
        model_call_count["value"] += 1
        if model_call_count["value"] == 1:
            await runner.queue_pending_user_message(raw_follow_up)
            return AIMessage(content="reply1")
        if model_call_count["value"] == 2:
            return AIMessage(content="reply2")
        raise AssertionError(
            f"unexpected extra model call: {model_call_count['value']}"
        )

    class _GraphWrapper:
        def __init__(self) -> None:
            self._graph = build_orchestrator_graph()

        async def astream_events(self, *args, **kwargs):
            async for event in self._graph.astream_events(*args, **kwargs):
                yield event

        async def aget_state(self, *_args, **_kwargs):
            return SimpleNamespace(
                next=(),
                tasks=[],
                values={},
                config={"configurable": {}},
            )

    async def fake_get_graph():
        return _GraphWrapper()

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", noop_emit)
    monkeypatch.setattr(
        "app.agent_runtime.graph.orchestrator.graph.create_chat_model",
        lambda _config: _FakeModel(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent.build_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent._invoke_model",
        fake_invoke_model,
    )
    monkeypatch.setattr(runner, "_get_graph", fake_get_graph)
    real_persister = runner._make_persister()
    monkeypatch.setattr(real_persister, "persist_node_event", noop_node_event)
    monkeypatch.setattr(runner, "_make_persister", lambda: real_persister)

    from app.agent_runtime.audit import stop_audit_queue

    try:
        await runner.run("help")
    finally:
        await stop_audit_queue()

    assert model_call_count["value"] == 2

    async with factory() as session:
        items = await repo.list_by_session(session, "session_x")

    user_messages = [
        (item.role, item.content, item.status)
        for item in items
        if item.role == "user"
    ]
    assert user_messages == [
        ("user", "help", "sent"),
        ("user", compiled_follow_up, "sent"),
    ]
    assert not [item for item in items if item.role == "user" and item.status == "pending"]
    assert runner._queued_user_messages == {}


@pytest.mark.asyncio
async def test_injected_follow_up_persists_after_assistant_reply(
    isolated_db,
    monkeypatch,
):
    factory = isolated_db
    raw_follow_up = 'follow-up<of-mention kind="volume" volume_id="vol_x" label="旧卷" />'
    compiled_follow_up = "follow-up\n> 引用卷：第一卷"

    async def noop_emit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", noop_emit)

    runner = SessionRunner(
        session_id="session_x",
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )
    persister = runner._make_persister()

    await runner._persist_user_message("help")
    await runner.queue_pending_user_message(raw_follow_up)
    queued_message_id = next(iter(runner._queued_user_messages))
    await persister.handle({
        "event": "on_chain_start",
        "name": "writer",
        "tags": ["agent_node"],
        "data": {},
    })
    await persister.handle({
        "event": "on_chat_model_start",
        "run_id": "run-1",
        "data": {},
    })
    await persister.handle({
        "event": "on_chat_model_end",
        "run_id": "run-1",
        "data": {"output": AIMessage(content="reply1")},
    })
    drained = await runner._drain_inject_queue()
    assert drained == [("user", compiled_follow_up, queued_message_id)]

    async with factory() as session:
        items = await repo.list_by_session(session, "session_x")

    conversation = [
        (item.role, item.content)
        for item in items
        if item.role in {"user", "assistant"}
    ]
    assert conversation == [
        ("user", "help"),
        ("assistant", "reply1"),
        ("user", compiled_follow_up),
    ]
    assert queued_message_id not in runner._queued_user_messages


@pytest.mark.asyncio
async def test_run_persists_messages_end_to_end(isolated_db, monkeypatch):
    """跑一次 run，确认持久化产生了至少一条 assistant complete。"""
    factory = isolated_db

    # 关掉 emit 副作用
    async def noop_emit(*_a, **_kw):
        return None

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", noop_emit)

    # 模拟 graph：astream_events 直接产出一段 chat_model_start/stream/end
    from langchain_core.messages import AIMessageChunk

    class _FakeGraph:
        async def astream_events(self, *_a, **_kw):
            yield {"event": "on_chat_model_start", "data": {}}
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": AIMessageChunk(content="hello")},
            }
            yield {"event": "on_chat_model_end", "data": {}}

        async def aget_state(self, *_a, **_kw):
            class _S:
                next = None
                tasks: list = []
                values: dict = {}
                config = {"configurable": {}}
            return _S()

    runner = SessionRunner(
        session_id="s_x", task_id="task_x",
        model_config={"max_context_tokens": 8000}, project_id="proj_x",
    )

    async def fake_get_graph():
        return _FakeGraph()

    monkeypatch.setattr(runner, "_get_graph", fake_get_graph)
    await runner.run("hi user")

    async with factory() as s:
        items = await repo.list_by_session(s, "s_x")
    assert any(m.role == "assistant" and m.status == "complete" and m.content == "hello"
               for m in items)


@pytest.mark.asyncio
async def test_run_emits_and_persists_cumulative_task_token_usage(isolated_db, monkeypatch):
    from langchain_core.messages import AIMessage

    from app.storage.models.task import Task

    factory = isolated_db
    captured_events: list[tuple[str, dict]] = []

    async with factory() as session:
        task = await session.get(Task, "task_x")
        assert task is not None
        task.token_input = 100
        task.token_output = 40
        task.token_cache = 8
        task.context_input_tokens = 100
        await session.commit()

    async def noop_emit(*_args, **_kwargs):
        return None

    class _FakePersister:
        async def handle(self, _event):
            return None

        async def mark_user_sent(self, _message_id):
            return None

        async def finalize(self, *, reason):
            return None

        async def persist_node_event(self, _payload):
            return None

    class _FakeGraph:
        async def astream_events(self, *_args, **_kwargs):
            yield {
                "event": "on_chat_model_end",
                "run_id": "run-1",
                "data": {
                    "output": AIMessage(
                        content="",
                        usage_metadata={
                            "input_tokens": 10,
                            "output_tokens": 6,
                            "total_tokens": 16,
                            "input_token_details": {"cache_read": 2},
                        },
                    ),
                },
            }
            yield {
                "event": "on_chat_model_end",
                "run_id": "run-2",
                "data": {
                    "output": AIMessage(
                        content="",
                        response_metadata={
                            "usage": {
                                "input_tokens": 5,
                                "output_tokens": 4,
                                "total_tokens": 9,
                                "cache_read_tokens": 1,
                            },
                        },
                    ),
                },
            }

        async def aget_state(self, *_args, **_kwargs):
            return SimpleNamespace(
                next=(),
                tasks=[],
                values={},
                config={"configurable": {}},
            )

    runner = SessionRunner(
        session_id="s_usage",
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )

    async def fake_emit_agent_event(name: str, payload: dict) -> None:
        if name in {"agent:usage", "agent:task_usage_delta"}:
            captured_events.append((name, payload))

    async def fake_get_graph():
        return _FakeGraph()

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", noop_emit)
    monkeypatch.setattr(runner, "_emit_agent_event", fake_emit_agent_event)
    monkeypatch.setattr(runner, "_get_graph", fake_get_graph)
    monkeypatch.setattr(runner, "_make_persister", lambda: _FakePersister())

    await runner.run("统计 token")

    assert [payload for name, payload in captured_events if name == "agent:usage"] == [
        {
            "session_id": "s_usage",
            "token_input": 110,
            "token_output": 46,
            "token_cache": 10,
            "context_input_tokens": 10,
            "context_length": 8000,
        },
        {
            "session_id": "s_usage",
            "token_input": 115,
            "token_output": 50,
            "token_cache": 11,
            "context_input_tokens": 5,
            "context_length": 8000,
        },
    ]
    assert [payload for name, payload in captured_events if name == "agent:task_usage_delta"] == [
        {
            "session_id": "s_usage",
            "task_id": "task_x",
            "token_input": 10,
            "token_output": 6,
            "token_cache": 2,
        },
        {
            "session_id": "s_usage",
            "task_id": "task_x",
            "token_input": 5,
            "token_output": 4,
            "token_cache": 1,
        },
    ]

    async with factory() as session:
        task = await session.get(Task, "task_x")
        assert task is not None
        assert task.token_input == 115
        assert task.token_output == 50
        assert task.token_cache == 11
        assert task.context_input_tokens == 5


@pytest.mark.asyncio
async def test_emit_persisted_task_usage_events_preserves_compaction_usage_kind(
    isolated_db,
    monkeypatch,
):
    captured_events: list[tuple[str, dict]] = []

    runner = SessionRunner(
        session_id="s_compaction_usage",
        task_id="task_x",
        model_config={"max_context_tokens": 8000},
        project_id="proj_x",
    )

    async def fake_emit_agent_event(name: str, payload: dict) -> None:
        if name in {"agent:usage", "agent:task_usage_delta"}:
            captured_events.append((name, payload))

    monkeypatch.setattr(runner, "_emit_agent_event", fake_emit_agent_event)

    await runner._emit_persisted_task_usage_events(
        {
            "usage_kind": "compaction",
            "usage": {
                "input_tokens": 7,
                "output_tokens": 3,
                "input_token_details": {"cache_read": 2},
            },
        }
    )

    assert [payload for name, payload in captured_events if name == "agent:usage"] == [
        {
            "session_id": "s_compaction_usage",
            "token_input": 7,
            "token_output": 3,
            "token_cache": 2,
            "context_input_tokens": 7,
            "context_length": 8000,
            "usage_kind": "compaction",
        }
    ]
    assert [payload for name, payload in captured_events if name == "agent:task_usage_delta"] == [
        {
            "session_id": "s_compaction_usage",
            "task_id": "task_x",
            "token_input": 7,
            "token_output": 3,
            "token_cache": 2,
            "usage_kind": "compaction",
        }
    ]


@pytest.mark.asyncio
async def test_sync_dispatch_subagent_continues_primary_run_until_done(
    isolated_db,
    monkeypatch,
):
    factory = isolated_db
    captured_emits: list[tuple[str, object]] = []
    captured_node_messages: list[list[dict]] = []
    model_call_count = {"value": 0}

    class _FakeModel:
        def bind_tools(self, _tools):
            return self

    async def noop_emit(name, payload=None, *_args, **_kwargs):
        captured_emits.append((name, payload))
        return None

    async def noop_node_event(*_args, **_kwargs):
        return None

    async def fake_build_context_parts(*, node_messages, **_kwargs):
        captured_node_messages.append(list(node_messages))
        return [
            ContextMessage(
                role="user",
                content=f"turn:{len(captured_node_messages)}",
                metadata={"part": "history", "seq": len(captured_node_messages)},
            )
        ]

    async def fake_invoke_model(_model, _messages):
        model_call_count["value"] += 1
        if model_call_count["value"] == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "dispatch-1",
                        "name": "dispatch_subagent",
                        "args": {
                            "agent_key": "writer",
                            "task": "write scene",
                            "input": {},
                            "metadata": {},
                        },
                    }
                ],
            )
        if model_call_count["value"] == 2:
            return AIMessage(content="primary completed")
        raise AssertionError(
            f"unexpected extra model call: {model_call_count['value']}"
        )

    class _FakeSubagentRunner:
        async def run(self, child_run_id: str) -> dict:
            from app.storage.database import create_session

            session = await create_session()
            try:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="writer completed",
                )
            finally:
                await session.close()
            return {"assistant_content": "writer completed"}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    runner = SessionRunner(
        session_id="session_x",
        task_id="task_x",
        model_config={
            "provider_type": "openai-compatible",
            "base_url": "https://example.test",
            "api_key": "test-key",
            "model_id": "test-model",
            "max_context_tokens": 8000,
        },
        project_id="proj_x",
    )

    monkeypatch.setattr("app.agent_runtime.runner.session_runner.emit", noop_emit)
    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", noop_emit)
    monkeypatch.setattr(
        "app.agent_runtime.graph.orchestrator.graph.create_chat_model",
        lambda _config: _FakeModel(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent.build_context_parts",
        fake_build_context_parts,
    )
    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent._invoke_model",
        fake_invoke_model,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.dispatch_subagent.make_subagent_runner",
        lambda **_kwargs: _FakeSubagentRunner(),
    )

    class _GraphWrapper:
        def __init__(self) -> None:
            self._graph = build_orchestrator_graph()

        async def astream_events(self, *args, **kwargs):
            async for event in self._graph.astream_events(*args, **kwargs):
                yield event

        async def aget_state(self, *_args, **_kwargs):
            return SimpleNamespace(
                next=(),
                tasks=[],
                values={},
                config={"configurable": {}},
            )

    async def fake_get_graph():
        return _GraphWrapper()

    monkeypatch.setattr(runner, "_get_graph", fake_get_graph)
    real_persister = runner._make_persister()
    monkeypatch.setattr(real_persister, "persist_node_event", noop_node_event)
    monkeypatch.setattr(runner, "_make_persister", lambda: real_persister)

    try:
        await runner.run("help")
    finally:
        await get_agent_run_registry().cancel_all()

    assert model_call_count["value"] == 2
    done_payloads = [
        payload for name, payload in captured_emits if name == "agent:done"
    ]
    assert done_payloads
    assert all(
        isinstance(payload.get("created_at"), str) and payload["created_at"]
        for payload in done_payloads
    )
    assert any(
        any(
            message.get("role") == "tool"
            and message.get("tool_call_id") == "dispatch-1"
            for message in batch
        )
        for batch in captured_node_messages[1:]
    )
    dispatch_results = [
        payload
        for name, payload in captured_emits
        if name == "agent:tool_result"
        and isinstance(payload, dict)
        and payload.get("tool_call_id") == "dispatch-1"
    ]
    assert len(dispatch_results) == 1

    async with factory() as session:
        items = await repo.list_by_session(session, "session_x")
        child_runs = (
            await session.execute(select(AgentChildRun).order_by(AgentChildRun.created_at.asc()))
        ).scalars().all()

    assert any(
        item.role == "tool"
        and item.tool_name == "dispatch_subagent"
        and "writer completed" in item.content
        for item in items
    )
    assert len(child_runs) == 1
    assert child_runs[0].status == "completed"
