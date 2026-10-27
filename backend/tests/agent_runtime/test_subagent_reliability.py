import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.agent_runtime.persistence.child_runs import (
    MAX_ACTIVE_SUBAGENTS,
    complete_child_run_request,
    create_child_run,
    get_child_run_request_by_seq,
    recycle_child_run,
)
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentRunMessage,
)
from app.agent_runtime.tools.impls.orchestration import common
from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
    DispatchSubagentTool,
)
from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
    NotifySubagentTool,
)
from app.agent_runtime.runner.run_registry import AgentRunRegistry
from app.agent_runtime.tools.errors import ToolExecutionError
from app.storage.models.task import Task
from app.storage.models.project import Project


@pytest_asyncio.fixture
async def background_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/reliability.db")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project", title="Project"))
        session.add(Task(id="task", project_id="project", title="Task", mode="agent"))
        await session.commit()
    yield factory
    await engine.dispose()


async def child(factory, name="one", *, task="task", status="queued", limit=None):
    async with factory() as session:
        return await create_child_run(
            session,
            parent_session_id="parent" if task == "task" else "other-parent",
            parent_task_id=task,
            parent_thread_id="parent",
            child_thread_id=f"child-{name}",
            agent_key="explore",
            dispatch_id=name,
            tool_call_id=f"spawn-{name}",
            request={"task": "independent work"},
            status=status,
            metadata={"agent_number": f"#{1000 + sum(name.encode()) % 9000}"},
            max_active_children=limit,
        )


@pytest_asyncio.fixture
async def notify(background_db, monkeypatch):
    import app.agent_runtime.tools.impls.orchestration.notify_subagent as module

    monkeypatch.setattr(module, "ensure_primary", AsyncMock())
    monkeypatch.setattr(
        module, "latest_checkpoint_id_for_thread", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(module, "publish_child_user_message", AsyncMock())
    monkeypatch.setattr(common, "ensure_child_processing", AsyncMock(return_value=True))
    runner = SimpleNamespace(publish_parent_subagent_status=AsyncMock())
    monkeypatch.setattr(module, "make_subagent_runner", lambda **kwargs: runner)

    def tool(call="notify", revision=None, factory=background_db):
        result = NotifySubagentTool(
            _state={
                "session_id": "parent",
                "task_id": "task",
                "project_id": "project",
                "current_revision_id": revision,
            }
        )
        result._config = {"configurable": {"session_factory": factory}}
        result._tool_call_id = call
        return result

    return tool


async def counts(factory):
    async with factory() as session:
        return tuple(
            [
                (
                    await session.execute(select(func.count()).select_from(model))
                ).scalar_one()
                for model in (AgentChildRun, AgentChildRunRequest, AgentRunMessage)
            ]
        )


@pytest.mark.asyncio
async def test_concurrent_notification_replays_share_request_and_original_message(
    background_db, notify
):
    target = await child(background_db)
    results = await asyncio.gather(
        *[
            notify()._execute(
                target.dispatch_id, '原文\n"evidence" 🌙', background=True
            )
            for _ in range(12)
        ]
    )
    assert len({json.loads(item)["request_id"] for item in results}) == 1
    assert await counts(background_db) == (1, 2, 1)
    async with background_db() as session:
        request = (
            await session.execute(
                select(AgentChildRunRequest).where(
                    AgentChildRunRequest.request_kind == "notify"
                )
            )
        ).scalar_one()
        message = await session.get(AgentRunMessage, request.child_user_message_id)
        assert message.content == request.content == '原文\n"evidence" 🌙'
        assert request.child_user_message_seq == message.seq
        assert request.background


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["prompt", "mode", "target"])
async def test_replay_cannot_mutate_accepted_notification(
    background_db, notify, change
):
    target = await child(background_db)
    other = await child(background_db, "other")
    await notify()._execute(target.dispatch_id, "original", background=True)
    with pytest.raises(ToolExecutionError, match="cannot change") as conflict:
        await notify()._execute(
            other.dispatch_id if change == "target" else target.dispatch_id,
            "changed" if change == "prompt" else "original",
            background=change != "mode",
        )
    assert conflict.value.code == "conflict"
    assert await counts(background_db) == (2, 3, 1)


@pytest.mark.asyncio
async def test_new_call_or_revision_is_a_new_notification(background_db, notify):
    target = await child(background_db)
    results = [
        json.loads(
            await tool._execute(target.dispatch_id, "same text", background=True)
        )
        for tool in (notify("a", "rev-1"), notify("b", "rev-1"), notify("a", "rev-2"))
    ]
    assert len({item["request_id"] for item in results}) == 3
    assert await counts(background_db) == (1, 4, 3)


@pytest.mark.asyncio
async def test_completed_replay_does_not_restart_or_change_boundaries(
    background_db, notify
):
    target = await child(background_db)
    result = json.loads(
        await notify()._execute(target.dispatch_id, "work", background=True)
    )
    async with background_db() as session:
        await complete_child_run_request(
            session, result["request_id"], assistant_content="done"
        )
    replay = json.loads(
        await notify()._execute(target.dispatch_id, "work", background=True)
    )
    assert replay["request_id"] == result["request_id"]
    assert replay["status"] == "completed"
    common.ensure_child_processing.assert_awaited_once()
    assert await counts(background_db) == (1, 2, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("after_commit", [False, True])
async def test_notification_commit_failure_recovers_without_orphan_message(
    background_db, notify, after_commit
):
    target = await child(background_db)

    class CrashingSession(AsyncSession):
        async def commit(self):
            accepting = any(
                isinstance(row, AgentChildRunRequest) and row.source_call
                for row in self.new
            )
            if accepting and not after_commit:
                raise RuntimeError("interrupted acceptance")
            await super().commit()
            if accepting:
                raise RuntimeError("interrupted acceptance")

    crashing = async_sessionmaker(
        background_db.kw["bind"], class_=CrashingSession, expire_on_commit=False
    )
    with pytest.raises(RuntimeError, match="interrupted acceptance"):
        await notify(factory=crashing)._execute(
            target.dispatch_id, "once", background=True
        )
    assert await counts(background_db) == ((1, 2, 1) if after_commit else (1, 1, 0))
    await notify()._execute(target.dispatch_id, "once", background=True)
    assert await counts(background_db) == (1, 2, 1)


@pytest.mark.asyncio
async def test_simultaneous_admission_respects_task_tree_limit(background_db):
    results = await asyncio.gather(
        *[
            child(background_db, f"race-{i}", limit=MAX_ACTIVE_SUBAGENTS)
            for i in range(18)
        ],
        return_exceptions=True,
    )
    assert (
        sum(isinstance(item, AgentChildRun) for item in results) == MAX_ACTIVE_SUBAGENTS
    )
    assert all(
        isinstance(item, AgentChildRun) or "active subagents" in str(item)
        for item in results
    )
    assert await counts(background_db) == (10, 10, 0)


@pytest.mark.asyncio
async def test_dispatch_limit_covers_multiple_model_batches(background_db, monkeypatch):
    import app.agent_runtime.tools.impls.orchestration.dispatch_subagent as module

    monkeypatch.setattr(DispatchSubagentTool, "_validate_dispatch", AsyncMock())
    monkeypatch.setattr(
        module, "latest_checkpoint_id_for_thread", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        module,
        "persist_child_user_message",
        AsyncMock(return_value=SimpleNamespace(id="message", seq=0)),
    )
    monkeypatch.setattr(
        module,
        "make_subagent_runner",
        lambda **kwargs: SimpleNamespace(publish_parent_subagent_status=AsyncMock()),
    )
    monkeypatch.setattr(common, "ensure_child_processing", AsyncMock(return_value=True))
    for i in range(12):
        tool = DispatchSubagentTool(
            _state={"session_id": "parent", "task_id": "task", "project_id": "project"}
        )
        tool._config = {"configurable": {"session_factory": background_db}}
        tool._tool_call_id = f"batch-{i // 6}-call-{i}"
        if i < 10:
            await tool._execute("explore", "work", "work", background=True)
        else:
            with pytest.raises(ToolExecutionError, match="active subagents") as limit:
                await tool._execute("explore", "work", "work", background=True)
            assert limit.value.code == "limit_exceeded"
    assert await counts(background_db) == (10, 10, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("release", ["completed", "error", "cancelled", "recycled"])
async def test_completed_cancelled_or_recycled_child_releases_capacity(
    background_db, release
):
    first = await child(background_db, "first", limit=1)
    with pytest.raises(ValueError, match="active subagents"):
        await child(background_db, "blocked", limit=1)
    async with background_db() as session:
        if release == "recycled":
            await recycle_child_run(session, first.id)
        else:
            request = await get_child_run_request_by_seq(
                session, child_run_id=first.id, seq=0
            )
            await complete_child_run_request(session, request.id, status=release)
    await child(background_db, "replacement", limit=1)
    assert await counts(background_db) == (2, 2, 0)


@pytest.mark.asyncio
async def test_approval_holds_capacity_and_other_task_has_own_limit(background_db):
    await child(background_db, "approval", status="waiting_user", limit=1)
    with pytest.raises(ValueError, match="active subagents"):
        await child(background_db, "blocked", limit=1)
    async with background_db() as session:
        session.add(Task(id="other", project_id="project", title="Other", mode="agent"))
        await session.commit()
    await child(background_db, "independent", task="other", limit=1)


@pytest.mark.asyncio
async def test_idle_notify_requires_capacity_but_busy_notify_and_replay_do_not(
    background_db, notify
):
    idle = await child(background_db, "idle", status="completed")
    active = [await child(background_db, f"active-{i}", limit=10) for i in range(10)]
    with pytest.raises(ToolExecutionError, match="active subagents") as limit:
        await notify("idle")._execute(idle.dispatch_id, "work", background=True)
    assert limit.value.code == "limit_exceeded"
    assert await counts(background_db) == (11, 11, 0)
    await notify("active")._execute(active[0].dispatch_id, "work", background=True)
    await notify("active")._execute(active[0].dispatch_id, "work", background=True)
    assert await counts(background_db) == (11, 12, 1)


@pytest.mark.asyncio
async def test_cancelling_runner_retains_slot_until_cleanup_finishes(
    background_db, monkeypatch
):
    registry = AgentRunRegistry()
    monkeypatch.setattr(
        "app.agent_runtime.runner.run_registry.get_agent_run_registry",
        lambda: registry,
    )
    target = await child(background_db, "closing", limit=1)
    started, cancelling, release = (asyncio.Event() for _ in range(3))

    async def slow_cleanup():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelling.set()
            await release.wait()

    task = asyncio.create_task(slow_cleanup())
    try:
        await registry.register_child("parent", target.id, task)
        await started.wait()
        await registry.cancel_child("parent", target.id)
        await cancelling.wait()
        async with background_db() as session:
            request = await get_child_run_request_by_seq(
                session, child_run_id=target.id, seq=0
            )
            await complete_child_run_request(session, request.id, status="cancelled")
        with pytest.raises(ValueError, match="active subagents"):
            await child(background_db, "too-early", limit=1)
        release.set()
        await task
        await child(background_db, "after-cleanup", limit=1)
    finally:
        release.set()
        await registry.cancel_all()


@pytest.mark.asyncio
async def test_dispatch_and_idle_notifications_compete_for_same_capacity(
    background_db, notify
):
    idle = [
        await child(background_db, f"idle-{i}", status="completed") for i in range(8)
    ]
    results = await asyncio.gather(
        *[
            child(background_db, f"new-{i}", limit=MAX_ACTIVE_SUBAGENTS)
            for i in range(8)
        ],
        *[
            notify(f"wake-{i}")._execute(row.dispatch_id, "continue", background=True)
            for i, row in enumerate(idle)
        ],
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 10
    assert all(
        not isinstance(result, Exception) or "active subagents" in str(result)
        for result in results
    )
    async with background_db() as session:
        active = (
            (
                await session.execute(
                    select(AgentChildRun).where(AgentChildRun.status == "queued")
                )
            )
            .scalars()
            .all()
        )
        assert len(active) == 10
        request_count = (
            await session.execute(
                select(func.count()).select_from(AgentChildRunRequest)
            )
        ).scalar_one()
        assert request_count == 18


@pytest.mark.asyncio
async def test_distinct_concurrent_notifications_keep_distinct_messages_and_sequence(
    background_db, notify
):
    target = await child(background_db)
    results = await asyncio.gather(
        *[
            notify(f"notification-{i}")._execute(
                target.dispatch_id, f"message-{i}", background=True
            )
            for i in range(12)
        ]
    )
    assert len({json.loads(result)["request_id"] for result in results}) == 12
    assert await counts(background_db) == (1, 13, 12)
    async with background_db() as session:
        requests = (
            (
                await session.execute(
                    select(AgentChildRunRequest)
                    .where(AgentChildRunRequest.request_kind == "notify")
                    .order_by(AgentChildRunRequest.seq)
                )
            )
            .scalars()
            .all()
        )
        assert [request.seq for request in requests] == list(range(1, 13))
        for request in requests:
            message = await session.get(AgentRunMessage, request.child_user_message_id)
            assert message.content == request.content
            assert message.seq == request.child_user_message_seq
