import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.agent_runtime.graph.react_agent import create_react_agent
from app.agent_runtime.persistence.child_runs import (
    complete_child_run_request,
    create_child_run,
    enqueue_child_run_request,
    get_child_run_request_by_seq,
    rollback_child_runs_for_parent_revisions,
    recycle_child_run,
    update_child_run_status,
)
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence.model import AgentChildRunRequest, AgentRunMessage
from app.agent_runtime.runner.background_subagents import BackgroundSubagentMailbox
from app.agent_runtime.runner.run_registry import AgentRunRegistry
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration import common
from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
    DispatchSubagentTool,
)
from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
    NotifySubagentTool,
)
from app.agent_runtime.tools.impls.orchestration.wait_subagents import WaitSubagentsTool
from app.agent_runtime.types import ReactAgentConfig, TerminationCondition
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.task import Task


@pytest_asyncio.fixture
async def background_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/background.db")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project", title="Project"))
        session.add(Task(id="task", project_id="project", title="Task", mode="agent"))
        await session.commit()
    yield factory
    await engine.dispose()


async def make_child(factory, dispatch_id="dispatch", revision_id=None):
    async with factory() as session:
        child = await create_child_run(
            session,
            parent_session_id="parent",
            parent_task_id="task",
            parent_thread_id="parent",
            child_thread_id=f"parent:child:{dispatch_id}",
            agent_key="writer",
            dispatch_id=dispatch_id,
            tool_call_id=f"call-{dispatch_id}",
            request={"task": "write a scene"},
            parent_revision_id=revision_id,
        )
        request = await get_child_run_request_by_seq(
            session, child_run_id=child.id, seq=0
        )
        request.background = True
        await session.commit()
        return child, request


def mailbox(factory, session_id="parent"):
    return BackgroundSubagentMailbox(
        parent_session_id=session_id, project_id="project", session_factory=factory
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "error", "cancelled"])
async def test_background_results_are_persisted_once_and_replayed_after_model_failure(
    background_db, status
):
    child, request = await make_child(background_db)
    async with background_db() as session:
        await complete_child_run_request(
            session,
            request.id,
            status=status,
            assistant_content="scene" if status == "completed" else None,
            error="failed" if status != "completed" else None,
        )
    box = mailbox(background_db)
    assert await box.wait_until_ready()
    first = await box.collect()
    assert len(first) == 1
    payload = json.loads(first[0].content.split("\n", 1)[1])
    assert payload["request_id"] == request.id
    assert payload["dispatch_id"] == child.dispatch_id
    assert payload["status"] == status
    assert not await box.collect({first[0].id})
    # Simulate retrying a model call whose graph update was never committed.
    assert [m.id for m in await box.collect()] == [first[0].id]
    assert not await box.wait_until_ready()
    async with background_db() as session:
        history = await load_history(session, "parent")
        assert [m.id for m in history] == [first[0].id]
        rows = (await session.execute(select(AgentRunMessage))).scalars().all()
        assert len(rows) == 1
        assert rows[0].display_channel == "hidden"


@pytest.mark.asyncio
async def test_mailbox_does_not_mix_parents_and_keeps_each_request_result(
    background_db,
):
    child, request = await make_child(background_db)
    async with background_db() as session:
        followup = await enqueue_child_run_request(
            session, child_run_id=child.id, request_kind="notify", content="revise"
        )
        followup.background = True
        await session.commit()
        await complete_child_run_request(session, request.id, assistant_content="first")
        await complete_child_run_request(
            session, followup.id, assistant_content="second"
        )
    assert await mailbox(background_db, "another-parent").collect() == []
    messages = await mailbox(background_db).collect()
    assert len(messages) == 2
    assert len({m.response_metadata["openfic_seq"] for m in messages}) == 2
    assert [json.loads(m.content.split("\n", 1)[1])["result"] for m in messages] == [
        "first",
        "second",
    ]


@pytest.mark.asyncio
async def test_rolled_back_and_recycled_work_does_not_wake_parent(background_db):
    child, _ = await make_child(background_db, revision_id="revision")
    async with background_db() as session:
        await rollback_child_runs_for_parent_revisions(
            session, parent_revision_ids=["revision"]
        )
        await session.commit()
    box = mailbox(background_db)
    assert not await box.wait_until_ready()
    assert await box.collect() == []
    child, _ = await make_child(background_db, dispatch_id="recycled")
    async with background_db() as session:
        await recycle_child_run(session, child.id)
    assert not await box.wait_until_ready()
    assert await box.collect() == []


@pytest.mark.asyncio
async def test_waiting_mailbox_can_be_cancelled_or_interrupted_by_user_input(
    background_db,
):
    await make_child(background_db)
    box = mailbox(background_db)
    wait = asyncio.create_task(box.wait_until_ready())
    await asyncio.sleep(0.02)
    assert not wait.done()
    wait.cancel()
    with pytest.raises(asyncio.CancelledError):
        await wait
    inject_queue = asyncio.Queue()
    inject_queue.put_nowait((None, "user", "new information"))
    assert await box.wait_until_ready(inject_queue)


@pytest.mark.asyncio
async def test_background_start_is_nonblocking_and_child_remains_cancellable(
    background_db, monkeypatch
):
    child, request = await make_child(background_db)
    started, release = asyncio.Event(), asyncio.Event()
    registry = AgentRunRegistry()
    monkeypatch.setattr(common, "get_agent_run_registry", lambda: registry)

    class Runner:
        async def run(self, _child_run_id):
            started.set()
            await release.wait()

    result = await asyncio.wait_for(
        common.start_background_request(
            configurable={"session_factory": background_db},
            parent_session_id="parent",
            row=child,
            request_id=request.id,
            runner=Runner(),
        ),
        timeout=2,
    )
    await asyncio.wait_for(started.wait(), timeout=2)
    assert result["background"] is True
    assert result["request_id"] == request.id
    assert await registry.is_child_running("parent", child.id)
    assert await registry.cancel("parent")
    await registry.cancel_all()
    assert not await registry.is_running("parent")


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_kind", ["dispatch", "notify"])
async def test_dispatch_and_notify_background_return_without_waiting(
    background_db, monkeypatch, tool_kind
):
    from types import SimpleNamespace
    import app.agent_runtime.tools.impls.orchestration.dispatch_subagent as dispatch_module
    import app.agent_runtime.tools.impls.orchestration.notify_subagent as notify_module

    module = dispatch_module if tool_kind == "dispatch" else notify_module
    tool_class = DispatchSubagentTool if tool_kind == "dispatch" else NotifySubagentTool
    monkeypatch.setattr(common, "ensure_child_processing", AsyncMock(return_value=True))
    monkeypatch.setattr(
        module, "latest_checkpoint_id_for_thread", AsyncMock(return_value=None)
    )
    if tool_kind == "dispatch":
        monkeypatch.setattr(
            module,
            "persist_child_user_message",
            AsyncMock(return_value=SimpleNamespace(id="user-message", seq=0)),
        )
    else:
        monkeypatch.setattr(module, "publish_child_user_message", AsyncMock())
    runner = Mock()
    runner.publish_parent_subagent_status = AsyncMock()
    monkeypatch.setattr(module, "make_subagent_runner", lambda **_kwargs: runner)
    wait_for_result = AsyncMock(
        side_effect=AssertionError("background dispatch must not wait")
    )
    monkeypatch.setattr(tool_class, "_wait_for_assistant_content", wait_for_result)
    tool = tool_class(
        _state={
            "session_id": "parent",
            "task_id": "task",
            "project_id": "project",
        }
    )
    tool._config = {"configurable": {"session_factory": background_db}}
    tool._tool_call_id = "tool-call"
    if tool_kind == "dispatch":
        monkeypatch.setattr(DispatchSubagentTool, "_validate_dispatch", AsyncMock())
        result = json.loads(
            await tool._execute("writer", "write scene", "write scene", background=True)
        )
        replay = json.loads(
            await tool._execute("writer", "write scene", "write scene", background=True)
        )
        assert replay["dispatch_id"] == result["dispatch_id"]
        assert replay["request_id"] == result["request_id"]
    else:
        child, _request = await make_child(background_db)
        monkeypatch.setattr(module, "ensure_primary", AsyncMock())
        result = json.loads(
            await tool._execute(child.dispatch_id, "continue", background=True)
        )
    assert result["background"] is True
    wait_for_result.assert_not_awaited()
    async with background_db() as session:
        request = await session.get(AgentChildRunRequest, result["request_id"])
        assert request.background is True
        assert request.status == "pending"


@pytest.mark.asyncio
async def test_wait_subagents_timeout_does_not_cancel_and_rejects_foreign_children(
    background_db, monkeypatch
):
    import app.agent_runtime.tools.impls.orchestration.wait_subagents as wait_module

    child, request = await make_child(background_db)
    monkeypatch.setattr(wait_module, "ensure_primary", AsyncMock())
    tool = WaitSubagentsTool(_state={"session_id": "parent"})
    tool._config = {"configurable": {"session_factory": background_db}}
    assert json.loads(await tool._execute([child.dispatch_id], timeout_seconds=0)) == {
        "results": [],
        "timed_out": True,
    }
    async with background_db() as session:
        assert (await session.get(AgentChildRunRequest, request.id)).status == "pending"
        await complete_child_run_request(session, request.id, assistant_content="done")
    result = json.loads(await tool._execute([child.dispatch_id], timeout_seconds=0))
    assert result["results"][0]["result"] == "done"
    assert not result["timed_out"]
    async with background_db() as session:
        await enqueue_child_run_request(
            session, child_run_id=child.id, request_kind="notify", content="next"
        )
    # An older successful turn must not satisfy the wait for a new request.
    assert json.loads(await tool._execute([child.dispatch_id], timeout_seconds=0))[
        "timed_out"
    ]
    foreign = WaitSubagentsTool(_state={"session_id": "foreign"})
    foreign._config = tool._config
    with pytest.raises(ToolExecutionError, match="not found"):
        await foreign._execute([child.dispatch_id], timeout_seconds=0)


@pytest.mark.asyncio
async def test_background_runner_failure_before_claim_is_reported_without_hanging(
    background_db,
):
    child, request = await make_child(background_db)
    async with background_db() as session:
        await update_child_run_status(
            session, child.id, "error", error="model unavailable"
        )
    box = mailbox(background_db)
    assert await asyncio.wait_for(box.wait_until_ready(), timeout=1)
    messages = await box.collect()
    payload = json.loads(messages[0].content.split("\n", 1)[1])
    assert payload["status"] == "error"
    assert payload["error"] == "model unavailable"
    async with background_db() as session:
        assert (await session.get(AgentChildRunRequest, request.id)).status == "error"


@pytest.mark.asyncio
async def test_cancelled_parent_turn_does_not_deliver_late_results(background_db):
    async with background_db() as session:
        session.add(
            Revision(
                id="stopped-turn",
                project_id="project",
                message="cancelled turn",
                status="cancelled",
                project_snapshot_title="Project",
            )
        )
        await session.commit()
    child, request = await make_child(background_db, revision_id="stopped-turn")
    async with background_db() as session:
        await complete_child_run_request(
            session, request.id, assistant_content="late result"
        )
    box = mailbox(background_db)
    assert not await box.wait_until_ready()
    assert await box.collect() == []


@pytest.mark.asyncio
async def test_background_approval_waits_until_child_is_resumed(
    background_db, monkeypatch
):
    import app.agent_runtime.tools.impls.orchestration.wait_subagents as wait_module

    child, request = await make_child(background_db)
    async with background_db() as session:
        await update_child_run_status(session, child.id, "waiting_user")
    monkeypatch.setattr(wait_module, "ensure_primary", AsyncMock())
    tool = WaitSubagentsTool(_state={"session_id": "parent"})
    tool._config = {"configurable": {"session_factory": background_db}}
    result = json.loads(await tool._execute([child.dispatch_id], timeout_seconds=0))
    assert result["results"][0]["status"] == "waiting_user"
    assert not result["timed_out"]
    box = mailbox(background_db)
    wait = asyncio.create_task(box.wait_until_ready())
    try:
        await asyncio.sleep(0.02)
        assert not wait.done()
        async with background_db() as session:
            await complete_child_run_request(
                session, request.id, assistant_content="approved result"
            )
        assert await asyncio.wait_for(wait, timeout=2)
        assert "approved result" in (await box.collect())[0].content
    finally:
        wait.cancel()
        await asyncio.gather(wait, return_exceptions=True)


@pytest.mark.asyncio
async def test_parent_resumes_automatically_when_background_result_arrives(
    background_db, monkeypatch
):
    _child, request = await make_child(background_db)
    second_call = asyncio.Event()
    calls = []

    async def invoke(_model, messages, **_kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return AIMessage(content="Continuing independent work")
        assert any("background finding" in str(m.content) for m in messages)
        second_call.set()
        return AIMessage(content="Combined answer")

    monkeypatch.setattr("app.agent_runtime.graph.react_agent._invoke_model", invoke)
    model = Mock()
    model.bind_tools.return_value = model
    graph = create_react_agent(
        ReactAgentConfig(
            name="build",
            tools=[],
            termination=TerminationCondition(mode="no_tool_call"),
        ),
        model=model,
        background_subagents=mailbox(background_db),
    )
    parent = asyncio.create_task(
        graph.ainvoke({"messages": [HumanMessage(content="go")], "iteration_count": 0})
    )
    try:
        await asyncio.sleep(0.1)
        assert not parent.done()
        async with background_db() as session:
            await complete_child_run_request(
                session, request.id, assistant_content="background finding"
            )
        result = await asyncio.wait_for(parent, timeout=3)
        assert second_call.is_set()
        assert result["messages"][-1].content == "Combined answer"
        assert (
            len(
                [
                    m
                    for m in result["messages"]
                    if "background finding" in str(m.content)
                ]
            )
            == 1
        )
    finally:
        parent.cancel()
        await asyncio.gather(parent, return_exceptions=True)


@pytest.mark.asyncio
async def test_parent_can_use_tools_while_background_child_is_still_running(
    background_db, monkeypatch
):
    from types import SimpleNamespace
    import app.agent_runtime.tools.impls.orchestration.dispatch_subagent as dispatch_module

    registry = AgentRunRegistry()
    child_started, independent_done, parent_waiting, release = (
        asyncio.Event() for _ in range(4)
    )
    monkeypatch.setattr(common, "get_agent_run_registry", lambda: registry)
    monkeypatch.setattr(DispatchSubagentTool, "_validate_dispatch", AsyncMock())
    monkeypatch.setattr(
        dispatch_module, "latest_checkpoint_id_for_thread", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        dispatch_module,
        "persist_child_user_message",
        AsyncMock(return_value=SimpleNamespace(id="child-message", seq=0)),
    )

    class Runner:
        async def publish_parent_subagent_status(self, _child_id):
            pass

        async def run(self, child_id):
            child_started.set()
            await release.wait()
            async with background_db() as session:
                request = await get_child_run_request_by_seq(
                    session, child_run_id=child_id, seq=0
                )
                await complete_child_run_request(
                    session, request.id, assistant_content="child finding"
                )

    monkeypatch.setattr(
        dispatch_module, "make_subagent_runner", lambda **_kwargs: Runner()
    )

    async def independent_work() -> str:
        await asyncio.wait_for(child_started.wait(), timeout=2)
        assert not release.is_set()
        independent_done.set()
        return "independent work complete"

    call_count = 0

    async def invoke(_model, messages, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "dispatch",
                        "name": "dispatch_subagent",
                        "args": {
                            "agent_type": "writer",
                            "description": "scene",
                            "prompt": "write scene",
                            "background": True,
                        },
                    }
                ],
            )
        if call_count == 2:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "independent",
                        "name": "independent_work",
                        "args": {},
                    }
                ],
            )
        if call_count == 3:
            parent_waiting.set()
            return AIMessage(content="Independent work finished")
        assert any("child finding" in str(m.content) for m in messages)
        return AIMessage(content="Combined answer")

    monkeypatch.setattr("app.agent_runtime.graph.react_agent._invoke_model", invoke)
    model = Mock()
    model.bind_tools.return_value = model
    graph = create_react_agent(
        ReactAgentConfig(
            name="build",
            tools=[
                DispatchSubagentTool(
                    _state={
                        "session_id": "parent",
                        "task_id": "task",
                        "project_id": "project",
                    }
                ),
                StructuredTool.from_function(
                    coroutine=independent_work, description="Independent work"
                ),
            ],
            termination=TerminationCondition(mode="no_tool_call"),
        ),
        model=model,
        background_subagents=mailbox(background_db),
    )
    parent = asyncio.create_task(
        graph.ainvoke(
            {"messages": [HumanMessage(content="go")], "iteration_count": 0},
            config={"configurable": {"session_factory": background_db}},
        )
    )
    try:
        await asyncio.wait_for(parent_waiting.wait(), timeout=3)
        assert independent_done.is_set()
        assert not parent.done()
        release.set()
        result = await asyncio.wait_for(parent, timeout=3)
        assert result["messages"][-1].content == "Combined answer"
        assert call_count == 4
    finally:
        parent.cancel()
        release.set()
        await asyncio.gather(parent, return_exceptions=True)
        await registry.cancel_all()
