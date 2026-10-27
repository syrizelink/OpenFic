import asyncio
import base64
import json
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime import agent_board as board
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence.model import (
    AgentBoard,
    AgentBoardMessage,
    AgentBoardReadState,
)
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.board import BoardPostInput, BoardReadInput
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.task import Task
from app.storage.models.setting import Setting


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/board.db")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="p", title="Project"))
        session.add(Project(id="other-p", title="Other project"))
        session.add(
            Task(
                id="task",
                project_id="p",
                title="Task",
                mode="agent",
                agent_session_id="root",
            )
        )
        session.add(
            Task(
                id="other-task",
                project_id="p",
                title="Other task",
                mode="agent",
                agent_session_id="foreign",
            )
        )
        session.add(
            Revision(
                id="rev",
                project_id="p",
                message="Work",
                project_snapshot_title="Project",
            )
        )
        await session.commit()
        for child in ["a", "b"]:
            await create_child_run(
                session,
                parent_session_id="root",
                parent_task_id="task",
                parent_thread_id="root",
                child_thread_id=f"child-{child}",
                agent_key="explore",
                dispatch_id=child,
                tool_call_id=f"spawn-{child}",
                request={"task": child},
                parent_revision_id="rev",
            )
    yield factory
    await engine.dispose()


async def post(
    db,
    session_id="child-a",
    *,
    to="ALL",
    kind="INFO",
    body="第 3 章：阿青 19 岁；证据：原文第 42 行。",
    source="call",
    reply_to=None,
):
    async with db() as session:
        scope = await board.resolve_scope(session, session_id)
        return await board.post_message(
            session,
            scope,
            to=to,
            kind=kind,
            body=body,
            source_call=source,
            revision_id="rev",
            reply_to=reply_to,
        )


async def read(db, session_id="child-b", **kwargs):
    async with db() as session:
        return await board.read_messages(
            session, await board.resolve_scope(session, session_id), **kwargs
        )


@pytest.mark.asyncio
async def test_peers_exchange_exact_originals_and_reply_without_parent(db):
    original = await post(db, to="b")
    result = await read(db)
    assert result["self"] == "b"
    assert next(p for p in result["participants"] if p["self"])["id"] == "b"
    assert result["messages"][0]["body"] == original["body"]
    assert result["messages"][0]["from"] == "a"
    reply = await post(
        db,
        "child-b",
        to="a",
        kind="RESULT",
        body="更正：第 4 章记载 20 岁。",
        reply_to=original["id"],
    )
    assert reply["reply_to"] == original["id"]
    assert (await read(db, "child-a"))["messages"][-1]["body"] == reply["body"]


@pytest.mark.asyncio
async def test_board_isolation_and_no_identity_spoofing(db):
    original = await post(db)
    assert (await read(db, "foreign"))["messages"] == []
    async with db() as session:
        with pytest.raises(ToolExecutionError, match="not found"):
            await board.resolve_scope(session, "root", "other-p")
        with pytest.raises(ToolExecutionError, match="not found"):
            await board.resolve_scope(session, "missing")
    with pytest.raises(ToolExecutionError, match="participant"):
        await post(db, "foreign", to="a")
    with pytest.raises(ToolExecutionError, match="Reply"):
        await post(db, "foreign", reply_to=original["id"])
    with pytest.raises(ToolExecutionError, match="yourself"):
        await post(db, to="a")
    with pytest.raises(ValueError):
        BoardPostInput(to="ALL", type="INFO", body="text", sender="main")


@pytest.mark.asyncio
async def test_concurrent_posts_allocate_unique_ordered_sequences(db):
    await asyncio.gather(
        *[post(db, source=f"call-{i}", body=f"fact-{i}") for i in range(25)]
    )
    result = await read(db, limit=50)
    assert [m["seq"] for m in result["messages"]] == list(range(1, 26))
    assert len({m["id"] for m in result["messages"]}) == 25
    assert {m["body"] for m in result["messages"]} == {f"fact-{i}" for i in range(25)}


@pytest.mark.asyncio
async def test_concurrent_replayed_posts_are_idempotent(db):
    results = await asyncio.gather(*[post(db) for _ in range(10)])
    assert len({r["id"] for r in results}) == 1
    assert sum(r.get("duplicate", False) for r in results) == 9
    async with db() as session:
        stored = await session.get(AgentBoard, "root")
        assert (stored.sequence, stored.message_count) == (1, 1)
    with pytest.raises(ToolExecutionError, match="replayed"):
        await post(db, body="Changed replay")


@pytest.mark.asyncio
async def test_incremental_reads_and_view_do_not_claim_read_receipts(db):
    for i in range(5):
        await post(db, source=str(i), body=str(i))
    async with db() as session:
        scope = await board.resolve_scope(session, "child-b")
        assert await board.board_notice(session, scope)
        view = await board.board_view(session, scope, limit=2)
        assert [m["seq"] for m in view["messages"]] == [4, 5]
        assert view["next_before"] == 4
        assert await board.board_notice(session, scope)
    first = await read(db, limit=2)
    second = await read(db, since=first["cursor"], limit=2)
    last = await read(db, since=second["cursor"], limit=2)
    assert [m["seq"] for r in [first, second, last] for m in r["messages"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert not last["has_more"]
    assert (await read(db, since=last["cursor"]))["messages"] == []
    async with db() as session:
        assert not await board.board_notice(
            session, await board.resolve_scope(session, "child-b")
        )
    # An old page cannot move the persistent read watermark backwards.
    await read(db, limit=1)
    async with db() as session:
        assert not await board.board_notice(
            session, await board.resolve_scope(session, "child-b")
        )


@pytest.mark.asyncio
async def test_notifications_are_addressed_without_leaking_message_bodies(db):
    await post(db, to="main", body="PRIVATE_LOOKING_BUT_SHARED")
    async with db() as session:
        assert not await board.board_notice(
            session, await board.resolve_scope(session, "child-b")
        )
        notice = await board.board_notice(
            session, await board.resolve_scope(session, "root")
        )
        assert notice and "PRIVATE_LOOKING_BUT_SHARED" not in notice
    assert (await read(db))["messages"][0]["body"] == "PRIVATE_LOOKING_BUT_SHARED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor",
    [
        "invalid",
        "e30=",
        base64.urlsafe_b64encode(b'["foreign",0]').decode(),
        base64.urlsafe_b64encode(b'["root",99999]').decode(),
    ],
)
async def test_bad_and_foreign_cursors_are_rejected(db, cursor):
    with pytest.raises(ToolExecutionError, match="cursor"):
        await read(db, since=cursor)


@pytest.mark.asyncio
async def test_utf8_limits_and_quotas(db, monkeypatch):
    await post(db, body="🌙" * 1024)
    for body in [" ", "🌙" * 1025]:
        with pytest.raises(ToolExecutionError, match="UTF-8"):
            await post(db, body=body, source="invalid")
    monkeypatch.setattr(board, "MAX_MESSAGES", 1)
    with pytest.raises(ToolExecutionError, match="capacity"):
        await post(db, source="overflow")
    assert len((await read(db))["messages"]) == 1
    for limit in [0, 51]:
        with pytest.raises(ValueError):
            BoardReadInput(limit=limit)


@pytest.mark.asyncio
async def test_retraction_and_cancelled_authors(db):
    await post(db)
    async with db() as session:
        await board.retract_revisions(session, ["rev"])
        await session.commit()
    assert (await read(db))["messages"] == []
    async with db() as session:
        scope = await board.resolve_scope(session, "child-a")
        view = await board.board_view(session, scope)
        assert view["messages"][0]["retracted"]
        child = scope.child
        child.is_active = False
        session.add(child)
        await session.commit()
    with pytest.raises(ToolExecutionError, match="Inactive"):
        await post(db, source="retired")
    with pytest.raises(ToolExecutionError, match="Reply"):
        await post(db, "child-b", reply_to=view["messages"][0]["id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["open", "read", "close"])
async def test_board_context_degrades_once_and_recovers(db, monkeypatch, failure):
    from app.agent_runtime.tools.impls.orchestration import common

    context = board.AgentBoardContext("child-b", "p", db)
    logger = Mock()
    logger.bind.return_value = logger
    monkeypatch.setattr(board, "logger", logger)
    original_close = common.close_session

    async def failing_close(session):
        await original_close(session)
        raise RuntimeError("private failure details")

    for _ in range(2):
        with monkeypatch.context() as fault:
            if failure == "open":
                fault.setattr(
                    common,
                    "open_session",
                    AsyncMock(side_effect=RuntimeError("private failure details")),
                )
            elif failure == "read":
                fault.setattr(
                    board,
                    "board_notice",
                    AsyncMock(side_effect=RuntimeError("private failure details")),
                )
            else:
                fault.setattr(common, "close_session", failing_close)
            assert await context.prompt() == board.BOARD_UNAVAILABLE_NOTICE
    logger.warning.assert_called_once()
    restored = await context.prompt()
    assert "你的看板身份：b" in restored
    assert board.BOARD_UNAVAILABLE_NOTICE not in restored
    with monkeypatch.context() as fault:
        fault.setattr(
            board,
            "board_notice",
            AsyncMock(side_effect=RuntimeError("another failure")),
        )
        assert await context.prompt() == board.BOARD_UNAVAILABLE_NOTICE
    assert logger.warning.call_count == 2


@pytest.mark.asyncio
async def test_board_context_cancellation_propagates_and_closes_session(
    db, monkeypatch
):
    from app.agent_runtime.tools.impls.orchestration import common

    close = AsyncMock(wraps=common.close_session)
    monkeypatch.setattr(common, "close_session", close)
    monkeypatch.setattr(
        board, "board_notice", AsyncMock(side_effect=asyncio.CancelledError)
    )
    with pytest.raises(asyncio.CancelledError):
        await board.AgentBoardContext("child-b", "p", db).prompt()
    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_board_notice_failure_does_not_prevent_model_inference(db, monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage
    from app.agent_runtime.graph.react_agent import create_react_agent
    from app.agent_runtime.tools.impls.board import BoardReadTool
    from app.agent_runtime.types import ReactAgentConfig, TerminationCondition

    monkeypatch.setattr(
        board, "board_notice", AsyncMock(side_effect=RuntimeError("unavailable"))
    )
    invoke = AsyncMock(return_value=AIMessage(content="normal response"))
    monkeypatch.setattr("app.agent_runtime.graph.react_agent._invoke_model", invoke)
    model = Mock()
    model.bind_tools.return_value = model
    graph = create_react_agent(
        ReactAgentConfig(
            name="explore",
            tools=[BoardReadTool(_state={"session_id": "child-b", "project_id": "p"})],
            termination=TerminationCondition(mode="no_tool_call"),
        ),
        model=model,
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="continue")], "iteration_count": 0},
        config={
            "configurable": {"agent_board": board.AgentBoardContext("child-b", "p", db)}
        },
    )
    assert result["messages"][-1].content == "normal response"
    assert any(
        message.content == board.BOARD_UNAVAILABLE_NOTICE
        for message in invoke.call_args.args[1]
    )


@pytest.mark.asyncio
async def test_board_context_respects_disabled_read_permission(db):
    await post(db)
    context = board.AgentBoardContext("child-b", "p", db)
    text = await context.prompt()
    assert "未读取" in text
    assert "原文第 42 行" not in text
    async with db() as session:
        session.add(
            Setting(
                key="agent_tool_permissions",
                value=json.dumps([{"tool_name": "board_read", "mode": "deny"}]),
            )
        )
        await session.commit()
    assert await context.prompt() == ""


@pytest.mark.asyncio
async def test_read_is_bounded_even_with_many_large_messages(db):
    for i in range(10):
        await post(db, source=str(i), body="🌙" * 1024)
    result = await read(db, limit=50)
    assert result["has_more"]
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= board.MAX_READ_BYTES


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["cancelled", "rolled_back"])
async def test_stale_revision_cannot_publish_after_cancellation_or_rollback(db, status):
    async with db() as stale:
        scope = await board.resolve_scope(stale, "child-a")
        cached_revision = await stale.get(Revision, "rev")
        async with db() as writer:
            revision = await writer.get(Revision, "rev")
            revision.status = status
            await writer.commit()
        assert cached_revision.status == "active"
        with pytest.raises(ToolExecutionError, match="Cancelled or rolled back"):
            await board.post_message(
                stale,
                scope,
                to="ALL",
                kind="INFO",
                body="obsolete",
                source_call="stale",
                revision_id="rev",
            )
    assert (await read(db))["messages"] == []


@pytest.mark.asyncio
async def test_stale_child_identity_cannot_publish_after_deactivation(db):
    async with db() as stale:
        scope = await board.resolve_scope(stale, "child-a")
        async with db() as writer:
            current = await board.resolve_scope(writer, "child-a")
            current.child.is_active = False
            await writer.commit()
        assert scope.child.is_active
        with pytest.raises(ToolExecutionError, match="Inactive"):
            await board.post_message(
                stale,
                scope,
                to="ALL",
                kind="INFO",
                body="obsolete",
                source_call="stale",
                revision_id="rev",
            )
    assert (await read(db))["messages"] == []


@pytest.mark.asyncio
async def test_byte_quota_rejects_without_consuming_sequence_and_replays_still_work(
    db, monkeypatch
):
    monkeypatch.setattr(board, "MAX_BOARD_BYTES", 8)
    first = await post(db, body="12345678")
    assert (await post(db, body="12345678"))["id"] == first["id"]
    with pytest.raises(ToolExecutionError, match="capacity"):
        await post(db, source="extra", body="9")
    async with db() as session:
        persisted = await session.get(AgentBoard, "root")
        assert (
            persisted.sequence,
            persisted.message_count,
            persisted.message_bytes,
        ) == (1, 1, 8)


@pytest.mark.asyncio
async def test_cached_board_counter_refreshes_after_other_writer(db):
    await post(db, source="first")
    async with db() as stale:
        scope = await board.resolve_scope(stale, "child-b")
        cached = await stale.get(AgentBoard, "root")
        assert cached.sequence == 1
        await post(db, source="second")
        third = await board.post_message(
            stale,
            scope,
            to="ALL",
            kind="RESULT",
            body="third",
            source_call="third",
            revision_id="rev",
        )
        assert third["seq"] == 3
    assert [message["seq"] for message in (await read(db))["messages"]] == [1, 2, 3]


@pytest.mark.asyncio
async def test_large_roster_preserves_self_and_bounded_reads(db):
    async with db() as session:
        for i in range(55):
            await create_child_run(
                session,
                parent_session_id="root",
                parent_task_id="task",
                parent_thread_id="root",
                child_thread_id=f"new-child-{i}",
                agent_key="协作代理" * 16,
                dispatch_id=f"new-{i}",
                tool_call_id=f"spawn-{i}",
                request={},
                parent_revision_id="rev",
            )
        scope = await board.resolve_scope(session, "child-a")
        roster, truncated = await board.participants(session, scope)
        assert truncated and len(roster) == 50
        assert any(person["id"] == "a" and person["self"] for person in roster)
    for i in range(10):
        await post(db, source=str(i), body="🌙" * 1024)
    result = await read(db, "child-a", limit=50)
    assert result["participants_truncated"] and result["has_more"]
    assert {"main", "a"}.issubset({person["id"] for person in result["participants"]})
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= board.MAX_READ_BYTES


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["one", "all", "orphan"])
async def test_task_cleanup_removes_board_and_preserves_other_tasks(db, operation):
    from app.storage.services import task_service

    await post(db)
    await post(db, "foreign", source="foreign", body="other task")
    await read(db)
    await read(db, "foreign")
    async with db() as session:
        if operation == "one":
            await task_service.delete_task(session, "task")
        elif operation == "all":
            await task_service.delete_all_tasks(session, "p")
        else:
            await session.execute(delete(Task).where(Task.id == "task"))
            await session.commit()
            await task_service.cleanup_orphaned_task_data(session)
        await session.commit()
        for model in (AgentBoard, AgentBoardMessage, AgentBoardReadState):
            count = (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one()
            assert count == (0 if operation == "all" else 1)
    if operation != "all":
        assert (await read(db, "foreign"))["messages"][0]["body"] == "other task"


@pytest.mark.asyncio
async def test_first_post_waiting_for_rollback_cannot_publish_stale_fact(
    db, monkeypatch
):
    async with db() as setup:
        revision = await setup.get(Revision, "rev")
        revision.agent_session_id = "root"
        revision.task_id = "task"
        await setup.commit()
    started = asyncio.Event()
    original_ensure = board._ensure_board

    async def observed_ensure(session, scope):
        if scope.participant == "a":
            started.set()
        await original_ensure(session, scope)

    monkeypatch.setattr(board, "_ensure_board", observed_ensure)
    async with db() as rollback:
        await board.retract_revisions(rollback, ["rev"])
        revision = await rollback.get(Revision, "rev")
        revision.status = "rolled_back"
        posting = asyncio.create_task(post(db, body="stale first fact"))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            await rollback.commit()
            with pytest.raises(ToolExecutionError, match="Cancelled or rolled back"):
                await asyncio.wait_for(posting, timeout=5)
        finally:
            if not posting.done():
                posting.cancel()
                await asyncio.gather(posting, return_exceptions=True)
    async with db() as check:
        persisted = await check.get(AgentBoard, "root")
        assert persisted.sequence == 0 and persisted.message_count == 0
    assert (await read(db))["messages"] == []
