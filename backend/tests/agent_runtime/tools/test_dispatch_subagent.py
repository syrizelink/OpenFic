import asyncio
import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.graph.react_agent import create_react_agent
from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.child_runs import (
    claim_next_child_run_request,
    complete_child_run_request,
    create_child_run,
    get_child_run_request_by_seq,
    record_child_run_pending_approval,
)
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentDefinitionRecord,
)
from app.agent_runtime.types import ReactAgentConfig, TerminationCondition
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncGenerator:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(  # type: ignore[call-overload]
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-1", title="Project"))
        session.add(
            Volume(
                id="volume-1",
                project_id="project-1",
                title="Volume",
                order=1,
                chapter_count=1,
            )
        )
        session.add(
            Chapter(
                id="chapter-1",
                project_id="project-1",
                volume_id="volume-1",
                title="Chapter",
                order=1,
            )
        )
        session.add(
            Task(
                id="task-1",
                project_id="project-1",
                title="Task",
                mode="agent",
                agent_session_id="parent-session",
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


def _tool_state(**overrides):
    state = {
        "session_id": "parent-session",
        "task_id": "task-1",
        "project_id": "project-1",
        "model_config": {"max_context_tokens": 8000},
        "active_agent": "primary",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "write",
        "installed_skill_ids": [],
        "current_revision_id": "revision-1",
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_dispatch_subagent_rejects_non_primary_callers(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    tool = DispatchSubagentTool(_state=_tool_state(active_agent="writer"))

    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "reviewer",
                "task": "review this",
                "input": {},
                "metadata": {},
            },
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                },
            },
        )
    )

    assert "error" in result
    assert "primary" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_subagent_rejects_removed_mode_argument(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Writer draft is ready.",
                )
            return {"assistant_content": "Writer draft is ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = DispatchSubagentTool(_state=_tool_state())

    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": "write chapter",
                "mode": "sync",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-removed-mode"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert "error" in result
    assert "mode" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_subagent_validates_max_ten_dispatches_per_pa_turn(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    tool = DispatchSubagentTool(_state=_tool_state(_dispatch_subagent_count=10))

    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": "write chapter",
                "input": {},
                "metadata": {},
            },
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                },
            },
        )
    )

    assert "error" in result
    assert "10" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_subagent_rejects_disabled_db_subagent(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    async with db_session_factory() as session:
        session.add(
            AgentDefinitionRecord(
                key="reviewer",
                display_name="Reviewer",
                kind="subagent",
                prompt_agent_name="reviewer",
                model_id=None,
                tool_category_keys_json=["chapter_read"],
                enabled_skill_ids_json=[],
                metadata_json={},
                enabled=False,
                order_index=4,
            )
        )
        await session.commit()

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "reviewer",
                "task": "review this",
                "input": {},
                "metadata": {},
            },
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                },
            },
        )
    )

    assert "error" in result
    assert "enabled subagent" in result["error"]


@pytest.mark.asyncio
async def test_sync_dispatch_creates_active_child_thread_and_returns_assistant_content(
    db_session_factory,
):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    published_child_run_ids: list[str] = []

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Writer draft is ready.",
                )
            return {"assistant_content": "Writer draft is ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            published_child_run_ids.append(child_run_id)

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": "write chapter",
                "input": {"chapter_id": "chapter-1"},
                "metadata": {"priority": "high"},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-1"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert result["assistant_content"] == "Writer draft is ready."
    assert "mode" not in result
    assert result["child_thread_id"] != "parent-session"
    assert result["is_active"] is True
    assert isinstance(result["agent_number"], str)
    assert result["agent_number"].startswith("#")
    assert len(result["agent_number"]) == 5
    assert result["metadata"]["agent_number"] == result["agent_number"]
    assert published_child_run_ids == [result["child_run_id"]]

    async with db_session_factory() as session:
        row = (
            await session.execute(select(AgentChildRun).where(AgentChildRun.id == result["child_run_id"]))
        ).scalar_one()
        requests = (
            await session.execute(
                select(AgentChildRunRequest)
                .where(AgentChildRunRequest.child_run_id == row.id)
                .order_by(AgentChildRunRequest.seq.asc())
            )
        ).scalars().all()

    assert row.is_active is True
    assert row.last_assistant_content == "Writer draft is ready."
    assert row.metadata_json["agent_number"] == result["agent_number"]
    assert len(requests) == 1
    assert requests[0].request_kind == "dispatch"
    assert requests[0].assistant_content == "Writer draft is ready."


@pytest.mark.asyncio
async def test_sync_dispatch_waits_for_existing_child_approval_without_interrupting_parent(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="parent-session:child:existing",
            agent_key="writer",
            dispatch_id="dispatch-existing",
            tool_call_id="tool-call-existing",
            request={"task": "write chapter", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-existing",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-existing",
                "tool_name": "write_chapter",
                "child_run_id": row.id,
            },
        )

    ensure_calls: list[dict[str, object]] = []

    class ResumeRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            raise AssertionError("must not start a new child run while approval is pending")

        async def resume(self, child_run_id: str, payload: dict) -> dict:
            raise AssertionError("must not resume the child from the parent dispatch path")

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    async def fake_ensure_child_processing(**kwargs):
        ensure_calls.append(kwargs)
        return False

    async def fake_wait_for_request_resolution(**_kwargs):
        return SimpleNamespace(
            child_run=SimpleNamespace(last_assistant_content="Approved writer reply."),
            request=SimpleNamespace(assistant_content="Approved writer reply."),
        )

    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.dispatch_subagent.ensure_child_processing",
        fake_ensure_child_processing,
        raising=False,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.dispatch_subagent.wait_for_request_resolution",
        fake_wait_for_request_resolution,
        raising=False,
    )

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": "write chapter",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-existing"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": ResumeRunner,
                },
            },
        )
    )

    assert ensure_calls == []
    assert result["assistant_content"] == "Approved writer reply."


@pytest.mark.asyncio
async def test_dispatch_subagent_keeps_agent_numbers_unique_across_active_and_closed_runs(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )
    from app.agent_runtime.tools.impls.orchestration.recycle_subagent import (
        RecycleSubagentTool,
    )

    number_values = iter([1234, 1234, 5678, 1234, 9012])

    def fake_randint(start: int, end: int) -> int:
        assert start == 1000
        assert end == 9999
        return next(number_values)

    monkeypatch.setattr(
        "app.agent_runtime.persistence.child_runs.random.randint",
        fake_randint,
        raising=False,
    )

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="numbered draft ready.",
                )
            return {"assistant_content": "numbered draft ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = DispatchSubagentTool(_state=_tool_state())
    first = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": "write chapter",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-number-1"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )
    second = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "reviewer",
                "task": "review chapter",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-number-2"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    recycle_tool = RecycleSubagentTool(_state=_tool_state())
    await recycle_tool.ainvoke(
        {"child_run_id": first["child_run_id"], "reason": "done"},
        config={
            "configurable": {
                "thread_id": "parent-session",
                "session_factory": db_session_factory,
                "subagent_runner_factory": FakeSubagentRunner,
            },
        },
    )

    third = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "composer",
                "task": "compose chapter",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-number-3"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert first["agent_number"] == "#1234"
    assert second["agent_number"] == "#5678"
    assert third["agent_number"] == "#9012"
    assert len({first["agent_number"], second["agent_number"], third["agent_number"]}) == 3


@pytest.mark.asyncio
async def test_dispatch_subagent_persists_and_emits_primary_message_on_child_thread(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Draft the next scene.",
                )
            return {"assistant_content": "Draft the next scene."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.common.emit",
        fake_emit,
        raising=False,
    )
    raw_task = 'Draft the next scene.<of-mention kind="chapter" chapter_id="chapter-1" label="旧章节" />'
    compiled_task = "Draft the next scene.\n> 引用章节：Chapter"

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": raw_task,
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-child-user"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    async with db_session_factory() as session:
        child_messages = await message_repo.list_by_session(
            session,
            result["child_thread_id"],
        )

    assert [
        (
            message.role,
            message.agent_id,
            message.status,
            message.content,
            message.message_type,
        )
        for message in child_messages
    ] == [
        (
            "user",
            "primary",
            "sent",
            compiled_task,
            "user_request",
        )
    ]
    assert emitted == [
        (
            "agent:text",
            {
                "session_id": result["child_thread_id"],
                "message_id": child_messages[0].id,
                "correlation_id": child_messages[0].id,
                "created_at": child_messages[0].created_at.isoformat(),
                "updated_at": child_messages[0].updated_at.isoformat(),
                "type": "text",
                "role": "user",
                "status": "completed",
                "display": "list",
                "content": compiled_task,
                "payload": {"kind": "user_request"},
            },
            f"agent_subagent_session:{result['child_thread_id']}",
        )
    ]


@pytest.mark.asyncio
async def test_sync_dispatch_surfaces_child_processing_failure_instead_of_hanging(
    db_session_factory,
):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    class CrashingSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, _child_run_id: str) -> dict:
            raise RuntimeError("child runner crashed")

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await asyncio.wait_for(
            tool.ainvoke(
                {
                    "agent_key": "writer",
                    "task": "write chapter",
                    "input": {},
                    "metadata": {},
                },
                config={
                    "metadata": {"tool_call_id": "tool-call-crash"},
                    "configurable": {
                        "thread_id": "parent-session",
                        "session_factory": db_session_factory,
                        "subagent_runner_factory": CrashingSubagentRunner,
                    },
                },
            ),
            timeout=2,
        )
    )

    assert result["error"] == "subagent processing failed: child runner crashed"


@pytest.mark.asyncio
async def test_notify_subagent_returns_assistant_content_on_same_thread(
    db_session_factory,
):
    from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
        NotifySubagentTool,
    )

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-persistent",
            agent_key="writer",
            dispatch_id="dispatch-persistent",
            tool_call_id="tool-call-persistent",
            request={"task": "write", "input": {}},
        )
        first_request = await get_child_run_request_by_seq(
            session,
            child_run_id=row.id,
            seq=0,
        )
        assert first_request is not None
        await complete_child_run_request(
            session,
            first_request.id,
            assistant_content="First draft ready.",
        )

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Revised ending ready.",
                )
            return {"assistant_content": "Revised ending ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = NotifySubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "child_run_id": row.id,
                "message": "Please revise the ending.",
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "notify-call-1"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    async with db_session_factory() as session:
        persisted = await session.get(AgentChildRun, row.id)
    assert persisted is not None
    assert result["tool_call_id"] == "notify-call-1"
    assert result["assistant_content"] == "Revised ending ready."
    assert result["agent_key"] == "writer"
    assert result["agent_number"] == persisted.metadata_json["agent_number"]
    assert result["metadata"]["agent_number"] == persisted.metadata_json["agent_number"]
    assert persisted.child_thread_id == "child-thread-persistent"
    assert persisted.last_assistant_content == "Revised ending ready."


@pytest.mark.asyncio
async def test_notify_subagent_rejects_removed_expect_reply_argument(
    db_session_factory,
):
    from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
        NotifySubagentTool,
    )

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-approval",
            agent_key="writer",
            dispatch_id="dispatch-approval",
            tool_call_id="tool-call-approval",
            request={"task": "write", "input": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-1",
            approval_request={"type": "tool_approval", "approval_id": "approval-1"},
        )

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = NotifySubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "child_run_id": row.id,
                "message": "Queue this until approval is done.",
                "expect_reply": False,
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "notify-call-queued"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert "error" in result
    assert "expect_reply" in result["error"]


@pytest.mark.asyncio
async def test_notify_subagent_persists_and_emits_primary_message_on_child_thread(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
        NotifySubagentTool,
    )

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-notify-user",
            agent_key="writer",
            dispatch_id="dispatch-notify-user",
            tool_call_id="tool-call-notify-user",
            request={"task": "write", "input": {}},
            status="completed",
        )

    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Follow-up is ready.",
                )
            return {"assistant_content": "Follow-up is ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.common.emit",
        fake_emit,
        raising=False,
    )
    raw_message = (
        'Queue this follow-up for later.'
        '<of-mention kind="chapter" chapter_id="chapter-1" label="旧章节" />'
    )
    compiled_message = "Queue this follow-up for later.\n> 引用章节：Chapter"

    tool = NotifySubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "child_run_id": row.id,
                "message": raw_message,
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "notify-call-child-user"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert result["tool_call_id"] == "notify-call-child-user"
    assert result["child_run_id"] == row.id
    assert result["assistant_content"] == "Follow-up is ready."
    assert result["agent_key"] == "writer"
    assert isinstance(result["agent_number"], str)
    assert result["metadata"]["agent_number"] == result["agent_number"]

    async with db_session_factory() as session:
        child_messages = await message_repo.list_by_session(
            session,
            row.child_thread_id,
        )

    assert [
        (
            message.role,
            message.agent_id,
            message.status,
            message.content,
            message.message_type,
        )
        for message in child_messages
    ] == [
        (
            "user",
            "primary",
            "sent",
            compiled_message,
            "user_request",
        )
    ]
    assert emitted == [
        (
            "agent:text",
            {
                "session_id": row.child_thread_id,
                "message_id": child_messages[0].id,
                "correlation_id": child_messages[0].id,
                "created_at": child_messages[0].created_at.isoformat(),
                "updated_at": child_messages[0].updated_at.isoformat(),
                "type": "text",
                "role": "user",
                "status": "completed",
                "display": "list",
                "content": compiled_message,
                "payload": {"kind": "user_request"},
            },
            "agent_subagent_session:child-thread-notify-user",
        )
    ]


@pytest.mark.asyncio
async def test_notify_subagent_restarts_after_child_run_shutdown(
    db_session_factory,
):
    from app.agent_runtime.runner.run_registry import get_agent_run_registry
    from app.agent_runtime.runner.subagent_runner import SubagentRunner
    from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
        NotifySubagentTool,
    )

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-race",
            agent_key="writer",
            dispatch_id="dispatch-race",
            tool_call_id="tool-call-race",
            request={"task": "write", "input": {}},
            status="running",
        )
        running_request = await get_child_run_request_by_seq(
            session,
            child_run_id=row.id,
            seq=0,
        )
        assert running_request is not None
        assert running_request.status == "running"

    finish_current_run = asyncio.Event()
    takeover_run_calls: list[str] = []

    async def existing_child_run() -> None:
        await finish_current_run.wait()
        async with db_session_factory() as session:
            current_request = await get_child_run_request_by_seq(
                session,
                child_run_id=row.id,
                seq=0,
            )
            assert current_request is not None
            await complete_child_run_request(
                session,
                current_request.id,
                assistant_content="final output before notify pickup",
            )
        await registry.unregister_child("parent-session", row.id)
        await recovery_runner.on_child_processing_finished(
            parent_session_id="parent-session",
            child_run_id=row.id,
        )

    class FakeSubagentRunner(SubagentRunner):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        async def run(self, child_run_id: str) -> dict:
            takeover_run_calls.append(child_run_id)
            assert self.session_factory is not None
            async with self.session_factory() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="follow-up reply",
                )
            return {"assistant_content": "follow-up reply"}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    registry = get_agent_run_registry()
    recovery_runner = FakeSubagentRunner(
        session_factory=db_session_factory,
        model_config={"max_context_tokens": 8000},
        project_id="project-1",
    )
    existing_task = asyncio.create_task(existing_child_run())
    await registry.register_child("parent-session", row.id, existing_task)

    tool = NotifySubagentTool(_state=_tool_state())
    notify_task = asyncio.create_task(
        tool.ainvoke(
            {
                "child_run_id": row.id,
                "message": "Continue after your current reply.",
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "notify-call-race"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    for _ in range(20):
        async with db_session_factory() as session:
            queued_request = await get_child_run_request_by_seq(
                session,
                child_run_id=row.id,
                seq=1,
            )
            if queued_request is not None:
                break
        await asyncio.sleep(0.05)
    else:
        pytest.fail("notify request was not enqueued")

    finish_current_run.set()
    await existing_task

    result = json.loads(await asyncio.wait_for(notify_task, timeout=2))

    async with db_session_factory() as session:
        queued_request = await get_child_run_request_by_seq(
            session,
            child_run_id=row.id,
            seq=1,
        )
        updated_row = await session.get(AgentChildRun, row.id)

    assert result["tool_call_id"] == "notify-call-race"
    assert result["assistant_content"] == "follow-up reply"
    assert result["agent_key"] == "writer"
    assert isinstance(result["agent_number"], str)
    assert queued_request is not None
    assert queued_request.status == "completed"
    assert updated_row is not None
    assert result["metadata"]["agent_number"] == updated_row.metadata_json["agent_number"]
    assert updated_row.status == "completed"
    assert takeover_run_calls == [row.id]

    await registry.unregister_child("parent-session", row.id)


@pytest.mark.asyncio
async def test_recycle_subagent_marks_thread_inactive_and_later_notify_fails(
    db_session_factory,
):
    from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
        NotifySubagentTool,
    )
    from app.agent_runtime.tools.impls.orchestration.recycle_subagent import (
        RecycleSubagentTool,
    )

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-recycle",
            agent_key="writer",
            dispatch_id="dispatch-recycle",
            tool_call_id="tool-call-recycle",
            request={"task": "write", "input": {}},
        )

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    recycle_tool = RecycleSubagentTool(_state=_tool_state())
    recycled = json.loads(
        await recycle_tool.ainvoke(
            {"child_run_id": row.id, "reason": "done"},
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )
    notify_tool = NotifySubagentTool(_state=_tool_state())
    failed_notify = json.loads(
        await notify_tool.ainvoke(
            {
                "child_run_id": row.id,
                "message": "continue",
                "metadata": {},
            },
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert recycled["child_run_id"] == row.id
    assert recycled["tool_call_id"] is None
    assert recycled["recycled"] is True
    assert recycled["agent_key"] == "writer"
    assert isinstance(recycled["agent_number"], str)
    assert recycled["metadata"]["agent_number"] == recycled["agent_number"]
    assert "inactive" in failed_notify["error"]


@pytest.mark.asyncio
async def test_react_agent_parallelizes_only_dispatch_subagent_with_isolated_sessions(monkeypatch):
    events: list[str] = []
    created_sessions: list[object] = []
    seen_dispatch_sessions: list[object] = []
    shared_session = object()

    class FakeSession:
        async def close(self) -> None:
            events.append("session-closed")

    def session_factory():
        session = FakeSession()
        created_sessions.append(session)
        return session

    async def dispatch_subagent(name: str) -> str:
        events.append(f"dispatch-start:{name}")
        await asyncio.sleep(0.01)
        events.append(f"dispatch-end:{name}")
        return f"dispatch:{name}"

    async def ordered_tool(value: str) -> str:
        events.append(f"ordered:{value}")
        assert "dispatch-start:first" in events
        assert "dispatch-start:second" in events
        return f"ordered:{value}"

    dispatch_tool = StructuredTool.from_function(
        coroutine=dispatch_subagent,
        name="dispatch_subagent",
        description="dispatch",
    )
    ordered = StructuredTool.from_function(
        coroutine=ordered_tool,
        name="ordered_tool",
        description="ordered",
    )

    async def fake_invoke_model(_model, _messages):
        return AIMessage(
            content="",
            tool_calls=[
                {"id": "call-1", "name": "dispatch_subagent", "args": {"name": "first"}},
                {"id": "call-2", "name": "dispatch_subagent", "args": {"name": "second"}},
                {"id": "call-3", "name": "ordered_tool", "args": {"value": "after"}},
            ],
        )

    async def capture_invoke_tool(tool_instance, tool_args, tool_call=None, config=None):
        if tool_instance.name == "dispatch_subagent":
            seen_dispatch_sessions.append(config["configurable"]["db_session"])
            assert config["configurable"]["db_session"] is not shared_session
        return await tool_instance.ainvoke(tool_args, config=config)

    graph = create_react_agent(
        ReactAgentConfig(
            name="primary",
            tools=[dispatch_tool, ordered],
            termination=TerminationCondition(mode="no_tool_call"),
            max_iterations=1,
        )
    )

    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent._invoke_model",
        fake_invoke_model,
    )
    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent._invoke_tool",
        capture_invoke_tool,
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="go")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        },
        config={
            "configurable": {
                "db_session": shared_session,
                "session_factory": session_factory,
            }
        },
    )

    tool_messages = result["messages"][-3:]
    assert [message.tool_call_id for message in tool_messages] == [
        "call-1",
        "call-2",
        "call-3",
    ]
    assert events.index("ordered:after") > events.index("dispatch-start:first")
    assert events.index("ordered:after") > events.index("dispatch-start:second")
    assert len(created_sessions) == 2
    assert seen_dispatch_sessions == created_sessions
    assert seen_dispatch_sessions[0] is not seen_dispatch_sessions[1]
    assert seen_dispatch_sessions[0] is not shared_session
    assert seen_dispatch_sessions[1] is not shared_session


@pytest.mark.asyncio
async def test_dispatch_subagent_with_whitelist_allows_listed_subagent(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    async with db_session_factory() as session:
        session.add(
            AgentDefinitionRecord(
                key="primary",
                display_name="Primary Agent",
                kind="primary",
                prompt_agent_name="primary",
                model_id=None,
                tool_category_keys_json=["orchestration", "interaction", "chapter_read"],
                enabled_skill_ids_json=[],
                metadata_json={},
                enabled=True,
                source="builtin",
                delegatable_agents=["writer"],
                order_index=0,
            )
        )
        await session.commit()

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Writer draft ready.",
                )
            return {"assistant_content": "Writer draft ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "writer",
                "task": "write chapter",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-whitelist"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert result["assistant_content"] == "Writer draft ready."


@pytest.mark.asyncio
async def test_dispatch_subagent_with_whitelist_rejects_unlisted_subagent(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    async with db_session_factory() as session:
        session.add(
            AgentDefinitionRecord(
                key="primary",
                display_name="Primary Agent",
                kind="primary",
                prompt_agent_name="primary",
                model_id=None,
                tool_category_keys_json=["orchestration", "interaction", "chapter_read"],
                enabled_skill_ids_json=[],
                metadata_json={},
                enabled=True,
                source="builtin",
                delegatable_agents=["writer"],
                order_index=0,
            )
        )
        await session.commit()

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "reviewer",
                "task": "review this",
                "input": {},
                "metadata": {},
            },
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                },
            },
        )
    )

    assert "error" in result
    assert "whitelist" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_subagent_allows_custom_subagent_when_whitelisted(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    async with db_session_factory() as session:
        session.add(
            AgentDefinitionRecord(
                key="primary",
                display_name="Primary Agent",
                kind="primary",
                prompt_agent_name="primary",
                model_id=None,
                tool_category_keys_json=["orchestration", "interaction", "chapter_read"],
                enabled_skill_ids_json=[],
                metadata_json={},
                enabled=True,
                source="builtin",
                delegatable_agents=["custom-writer"],
                order_index=0,
            )
        )
        session.add(
            AgentDefinitionRecord(
                key="custom-writer",
                display_name="Custom Writer",
                kind="subagent",
                prompt_agent_name="writer",
                model_id=None,
                tool_category_keys_json=["chapter_read", "chapter_write"],
                enabled_skill_ids_json=[],
                metadata_json={},
                enabled=True,
                source="custom",
                order_index=10,
            )
        )
        await session.commit()

    class FakeSubagentRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run(self, child_run_id: str) -> dict:
            async with self.kwargs["session_factory"]() as session:
                claimed = await claim_next_child_run_request(session, child_run_id)
                assert claimed is not None
                await complete_child_run_request(
                    session,
                    claimed.id,
                    assistant_content="Custom writer draft ready.",
                )
            return {"assistant_content": "Custom writer draft ready."}

        async def publish_parent_subagent_status(self, child_run_id: str) -> None:
            return None

    tool = DispatchSubagentTool(_state=_tool_state())
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "custom-writer",
                "task": "write with custom agent",
                "input": {},
                "metadata": {},
            },
            config={
                "metadata": {"tool_call_id": "tool-call-custom"},
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                    "subagent_runner_factory": FakeSubagentRunner,
                },
            },
        )
    )

    assert result["assistant_content"] == "Custom writer draft ready."


@pytest.mark.asyncio
async def test_dispatch_subagent_rejects_non_primary_caller_via_definition_kind(db_session_factory):
    from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
        DispatchSubagentTool,
    )

    async with db_session_factory() as session:
        session.add(
            AgentDefinitionRecord(
                key="writer",
                display_name="Writer",
                kind="subagent",
                prompt_agent_name="writer",
                model_id=None,
                tool_category_keys_json=["chapter_read", "chapter_write"],
                enabled_skill_ids_json=[],
                metadata_json={},
                enabled=True,
                source="builtin",
                order_index=4,
            )
        )
        await session.commit()

    tool = DispatchSubagentTool(_state=_tool_state(active_agent="writer"))
    result = json.loads(
        await tool.ainvoke(
            {
                "agent_key": "reviewer",
                "task": "review this",
                "input": {},
                "metadata": {},
            },
            config={
                "configurable": {
                    "thread_id": "parent-session",
                    "session_factory": db_session_factory,
                },
            },
        )
    )

    assert "error" in result
    assert "primary" in result["error"].lower()
