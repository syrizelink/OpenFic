from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage
from langchain_core.messages import AIMessageChunk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.child_runs import (
    complete_child_run_request,
    create_child_run,
    enqueue_child_run_request,
    get_child_run_request_by_seq,
)
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentRunMessage,
)
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.setting import Setting
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


@pytest.fixture(autouse=True)
def stub_checkpointer(monkeypatch):
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.get_checkpointer",
        AsyncMock(return_value=object()),
    )


@pytest.mark.asyncio
async def test_resolve_agent_model_config_prefers_configured_default_setting(
    db_session_factory,
):
    from app.agent_runtime.runner.subagent_runner import (
        SYSTEM_DEFAULT_MODEL_REFERENCE,
        _resolve_agent_model_config,
    )
    from app.core.encryption import EncryptionService
    from app.models.entities.model import Model
    from app.models.entities.model_provider import ModelProvider
    from app.settings import settings

    api_key = EncryptionService(settings.encryption_key).encrypt("provider-key")

    async with db_session_factory() as session:
        session.add(
            ModelProvider(
                id="provider-default",
                url="https://default.example.com",
                api_key_encrypted=api_key,
                provider_type="openai",
            )
        )
        session.add(
            Model(
                id="model-default",
                name="Default",
                provider_id="provider-default",
                model_id="deepseek-v4-pro",
                context_length=64000,
            )
        )
        session.add(Setting(key="default_model", value="model-default"))
        await session.commit()

        resolved = await _resolve_agent_model_config(
            session,
            configured_model_id=SYSTEM_DEFAULT_MODEL_REFERENCE,
            inherited_config={
                "provider_type": "openai",
                "base_url": "",
                "api_key": "parent-key",
                "model_id": "model-parent",
                "max_context_tokens": 8000,
                "reasoning_effort": "high",
            },
        )

    assert resolved["model_id"] == "deepseek-v4-pro"
    assert resolved["provider_type"] == "openai"
    assert resolved["base_url"] == "https://default.example.com"
    assert resolved["api_key"] == "provider-key"
    assert resolved["max_context_tokens"] == 64000
    assert resolved["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_resolve_agent_model_config_falls_back_to_inherited_when_unconfigured(
    db_session_factory,
):
    from app.agent_runtime.runner.subagent_runner import (
        SYSTEM_DEFAULT_MODEL_REFERENCE,
        _resolve_agent_model_config,
    )

    inherited = {
        "provider_type": "openai",
        "base_url": "",
        "api_key": "parent-key",
        "model_id": "model-parent",
        "max_context_tokens": 8000,
    }

    async with db_session_factory() as session:
        resolved = await _resolve_agent_model_config(
            session,
            configured_model_id=SYSTEM_DEFAULT_MODEL_REFERENCE,
            inherited_config=inherited,
        )

    assert resolved == inherited
    assert resolved is not inherited


@pytest.mark.asyncio
async def test_subagent_runner_excludes_restricted_tools_from_definition(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.agents.definitions import AgentDefinition
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    captured: dict[str, list[str]] = {}

    def fake_get_tools(*, names, **_kwargs):
        captured["names"] = names
        return []

    async def fake_skill_tool_names(*_args, **_kwargs):
        return ()

    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.ToolRegistry.get_tools",
        fake_get_tools,
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.skill_tool_names_for_definition",
        fake_skill_tool_names,
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={},
        project_id="project-1",
    )
    definition = AgentDefinition(
        key="restricted-subagent",
        display_name="Restricted Subagent",
        description="",
        kind="subagent",
        prompt_agent_name="restricted-subagent",
        model_id=None,
        enabled_tool_categories=("orchestration", "interaction", "chapter_read"),
        enabled_skills=(),
        metadata={},
    )

    await runner._build_tools(definition, {})

    assert "dispatch_subagent" not in captured["names"]
    assert "notify_subagent" not in captured["names"]
    assert "recycle_subagent" not in captured["names"]
    assert "ask_user" not in captured["names"]
    assert "read_chapter" in captured["names"]


@pytest.mark.asyncio
async def test_subagent_runner_uses_child_thread_history_and_parent_task(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread",
            agent_key="writer",
            dispatch_id="dispatch-1",
            tool_call_id="tool-call-1",
            request={"task": "write", "input": {"chapter_id": "chapter-1"}},
        )
        session.add(
            AgentRunMessage(
                session_id="child-thread",
                task_id="task-1",
                project_id="project-1",
                role="user",
                content="child-only",
                status="sent",
                seq=0,
            )
        )
        await session.commit()

    captured: dict = {}

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            captured["initial_state"] = initial_state
            captured["config"] = config
            yield {
                "event": "on_chain_start",
                "name": "writer",
                "tags": ["agent_node", "subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_start",
                "run_id": "child-run-non-stream",
                "tags": ["subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_end",
                "run_id": "child-run-non-stream",
                "tags": ["subagent_child"],
                "data": {"output": AIMessage(content="Writer draft ready.")},
            }
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="Writer draft ready.")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="Writer draft ready.")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    async def fake_emit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    result = await runner.run(row.id)

    assert result["assistant_content"] == "Writer draft ready."
    runtime_state = captured["config"]["configurable"]["runtime_state"]
    assert runtime_state["session_id"] == "child-thread"
    assert runtime_state["task_id"] == "task-1"
    assert runtime_state["active_agent"] == "writer"

    async with db_session_factory() as session:
        child_messages = await repo.list_by_session(session, "child-thread")

    assert any(
        message.role == "assistant"
        and message.content == "Writer draft ready."
        and message.agent_id == "writer"
        for message in child_messages
    )
    assert [message.content for message in captured["initial_state"]["messages"]] == [
        "child-only",
        "write",
    ]
    assert captured["config"]["configurable"]["thread_id"] == "child-thread"
    assert "subagent_child" in captured["config"]["tags"]

    async with db_session_factory() as session:
        updated = await session.get(AgentChildRun, row.id)
    assert updated is not None
    assert updated.status == "completed"
    assert updated.last_assistant_content == "Writer draft ready."


@pytest.mark.asyncio
async def test_subagent_runner_uses_request_parent_revision_for_notify_turn(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        task = await session.get(Task, "task-1")
        assert task is not None
        task.current_revision_id = "rev-stale"
        session.add(task)
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-revision",
            agent_key="writer",
            dispatch_id="dispatch-revision",
            tool_call_id="tool-call-revision",
            request={"task": "first", "input": {}},
            status="completed",
            parent_revision_id="rev-1",
        )
        await enqueue_child_run_request(
            session,
            child_run_id=row.id,
            request_kind="notify",
            content="second",
            parent_revision_id="rev-2",
        )
        await session.commit()

    captured: dict = {}

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            captured["runtime_state"] = config["configurable"]["runtime_state"]
            yield {
                "event": "on_chat_model_end",
                "run_id": "child-run-revision",
                "tags": ["subagent_child"],
                "data": {"output": AIMessage(content="second done")},
            }
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="second done")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="second done")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    async def fake_emit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    await runner.run(row.id)

    assert captured["runtime_state"]["current_revision_id"] == "rev-2"


@pytest.mark.asyncio
async def test_subagent_runner_passes_compaction_sinks_to_child_graph(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-compaction",
            agent_key="writer",
            dispatch_id="dispatch-compaction",
            tool_call_id="tool-call-compaction",
            request={"task": "compact child context", "input": {}},
        )

    emitted: list[tuple[str, dict[str, Any], str | None]] = []
    persisted_usage: list[tuple[str, dict[str, Any]]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            assert config is not None
            configurable = config["configurable"]
            assert callable(configurable["agent_event_sink"])
            assert callable(configurable["compaction_usage_sink"])

            await configurable["agent_event_sink"](
                "agent:compaction_start",
                {
                    "session_id": "child-thread-compaction",
                    "task_id": "task-1",
                    "trigger": "auto",
                },
            )
            await configurable["compaction_usage_sink"](
                {
                    "usage_kind": "compaction",
                    "session_id": "child-thread-compaction",
                    "task_id": "task-1",
                    "trigger": "auto",
                    "usage": {
                        "input_tokens": 11,
                        "output_tokens": 3,
                        "input_token_details": {"cache_read": 2},
                    },
                }
            )
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="compacted child output")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="compacted child output")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    async def fake_persist_parent_usage(row_arg, payload):
        persisted_usage.append((row_arg.id, payload))

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    monkeypatch.setattr(
        runner,
        "_persist_parent_task_usage_and_emit_delta",
        fake_persist_parent_usage,
    )

    result = await runner.run(row.id)

    assert result["assistant_content"] == "compacted child output"
    assert (
        "agent:compaction_start",
        {
            "session_id": "child-thread-compaction",
            "task_id": "task-1",
            "trigger": "auto",
        },
        "agent_subagent_session:child-thread-compaction",
    ) in emitted
    assert persisted_usage == [
        (
            row.id,
            {
                "session_id": "child-thread-compaction",
                "parent_session_id": "parent-session",
                "usage_kind": "compaction",
                "token_input": 11,
                "token_output": 3,
                "token_cache": 2,
                "context_input_tokens": 11,
                "context_length": 8000,
            },
        )
    ]


@pytest.mark.asyncio
async def test_subagent_runner_keeps_parent_revision_available_for_writer_tools(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner
    from app.storage.models.revision import Revision

    async with db_session_factory() as session:
        revision = Revision(
            id="revision-1",
            project_id="project-1",
            message="Parent revision",
            agent_session_id="parent-session",
            status="active",
            revision_type="agent",
            is_checkpoint=True,
            task_id="task-1",
            project_snapshot_title="Project",
            project_snapshot_description=None,
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=1,
        )
        session.add(revision)
        task = await session.get(Task, "task-1")
        assert task is not None
        task.current_revision_id = revision.id
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-revision",
            agent_key="writer",
            dispatch_id="dispatch-revision",
            tool_call_id="tool-call-revision",
            request={"task": "write", "input": {"chapter_id": "chapter-1"}},
        )
        await session.commit()

    captured: dict[str, Any] = {}

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            captured["config"] = config
            captured["runtime_state"] = config["configurable"]["runtime_state"]
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="Writer draft ready.")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="Writer draft ready.")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    async def fake_emit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    await runner.run(row.id)

    runtime_state = captured["runtime_state"]
    assert captured["config"]["recursion_limit"] == 1000
    assert runtime_state["current_revision_id"] == "revision-1"


@pytest.mark.asyncio
async def test_subagent_runner_collects_subagent_audit_logs_with_parent_metadata(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-audit",
            agent_key="writer",
            dispatch_id="dispatch-audit",
            tool_call_id="tool-call-audit",
            request={"task": "write", "input": {"chapter_id": "chapter-1"}},
        )
        await session.commit()

    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    async def fake_emit(*_args, **_kwargs):
        return None

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            assert config is not None
            audit_context = config["configurable"]["audit_context"]
            yield {
                "event": "on_chain_start",
                "name": "writer",
                "tags": ["agent_node", "subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_start",
                "run_id": "child-run-audit",
                "tags": ["subagent_child"],
                "data": {},
            }
            async with audit_context.llm_call(
                operation="writer",
                model_id="gpt-test",
                model_provider="openai",
                request_messages=[],
            ) as audit:
                audit.record_response(
                    content="Writer draft ready.",
                    usage={
                        "input_tokens": 12,
                        "output_tokens": 4,
                        "total_tokens": 16,
                    },
                )
            yield {
                "event": "on_chat_model_end",
                "run_id": "child-run-audit",
                "tags": ["subagent_child"],
                "data": {"output": AIMessage(content="Writer draft ready.")},
            }
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="Writer draft ready.")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="Writer draft ready.")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )

    await runner.run(row.id)

    assert len(enqueued) == 1
    audit_log = enqueued[0]
    assert audit_log.session_id == "child-thread-audit"
    assert audit_log.task_id == "task-1"
    assert audit_log.parent_session_id == "parent-session"
    assert audit_log.child_run_id == row.id
    assert audit_log.operation == "writer"


@pytest.mark.asyncio
async def test_subagent_runner_drains_queued_notify_requests_on_same_child_thread(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-queue",
            agent_key="writer",
            dispatch_id="dispatch-queue",
            tool_call_id="tool-call-queue",
            request={"task": "initial", "input": {}},
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
            assistant_content="initial done",
        )
        await enqueue_child_run_request(
            session,
            child_run_id=row.id,
            request_kind="notify",
            content="second turn",
        )
        await enqueue_child_run_request(
            session,
            child_run_id=row.id,
            request_kind="notify",
            content="third turn",
        )

    async def fake_emit(*_args, **_kwargs):
        return None

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            last_message = initial_state["messages"][-1]
            yield {
                "event": "on_chain_end",
                "data": {"output": {
                    "messages": [AIMessage(content=f"reply:{last_message.content}")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            last_message = initial_state["messages"][-1]
            return {
                "messages": [AIMessage(content=f"reply:{last_message.content}")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    result = await runner.run(row.id)

    assert result["assistant_content"] == "reply:third turn"

    async with db_session_factory() as session:
        requests = (
            await session.execute(
                select(AgentChildRunRequest)
                .where(AgentChildRunRequest.child_run_id == row.id)
                .order_by(AgentChildRunRequest.seq.asc())
            )
        ).scalars().all()
        updated = await session.get(AgentChildRun, row.id)

    assert [(request.seq, request.status) for request in requests] == [
        (0, "completed"),
        (1, "completed"),
        (2, "completed"),
    ]
    assert updated is not None
    assert updated.child_thread_id == "child-thread-queue"
    assert updated.last_assistant_content == "reply:third turn"


@pytest.mark.asyncio
async def test_subagent_runner_records_pending_approval_and_resume_completes_same_request(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

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
        )
        await repo.insert_message(
            session,
            session_id="parent-session",
            task_id="task-1",
            project_id="project-1",
            role="tool",
            status="complete",
            content='{"assistant_content": "Writer draft ready."}',
            tool_call_id="tool-call-approval",
            tool_name="dispatch_subagent",
        )

    call_count = {"count": 0}
    emitted: list[tuple[str, dict[str, object], str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            call_count["count"] += 1
            if call_count["count"] == 1:
                yield {
                    "event": "on_chain_end",
                    "data": {"output": {
                        "messages": [],
                        "iteration_count": 1,
                        "is_done": False,
                        "final_output": None,
                        "__interrupt__": [
                            type(
                                "Interrupt",
                                (),
                                {
                                    "id": "approval-1",
                                    "value": {
                                        "type": "tool_approval",
                                        "approval_id": "approval-1",
                                        "tool_name": "write_chapter",
                                    },
                                },
                            )()
                        ],
                    }},
                }
                return
            yield {
                "event": "on_chain_end",
                "data": {"output": {
                    "messages": [AIMessage(content="Approved draft complete.")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return {
                    "messages": [],
                    "iteration_count": 1,
                    "is_done": False,
                    "final_output": None,
                    "__interrupt__": [
                        type(
                            "Interrupt",
                            (),
                            {
                                "id": "approval-1",
                                "value": {
                                    "type": "tool_approval",
                                    "approval_id": "approval-1",
                                    "tool_name": "write_chapter",
                                },
                            },
                        )()
                    ],
                }
            return {
                "messages": [AIMessage(content="Approved draft complete.")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.get_checkpointer",
        AsyncMock(return_value=object()),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    interrupted = await runner.run(row.id)
    resumed = await runner.resume(
        row.id,
        {
            "action_type": "tool_approval",
            "approval_id": "approval-1",
            "approved": True,
        },
    )

    assert interrupted["approval_request"]["approval_id"] == "approval-1"
    assert resumed["assistant_content"] == "Approved draft complete."

    parent_status_payloads = [
        payload
        for name, payload, room in emitted
        if name == "agent:subagent_status"
        and room == "agent_subagents:parent-session"
    ]
    assert any(
        payload.get("status") == "waiting_user"
        and payload.get("pending_approval", {}).get("approval_id") == "approval-1"
        for payload in parent_status_payloads
    )
    assert any(
        payload.get("status") == "running"
        and payload.get("pending_approval") is None
        for payload in parent_status_payloads
    )

    async with db_session_factory() as session:
        updated = await session.get(AgentChildRun, row.id)
        requests = (
            await session.execute(
                select(AgentChildRunRequest)
                .where(AgentChildRunRequest.child_run_id == row.id)
                .order_by(AgentChildRunRequest.seq.asc())
            )
        ).scalars().all()

    assert updated is not None
    assert updated.pending_approval_id is None
    assert updated.status == "completed"
    assert requests[0].status == "completed"
    assert requests[0].assistant_content == "Approved draft complete."


@pytest.mark.asyncio
async def test_subagent_runner_emits_child_interrupt_when_pending_tool_approval(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-interrupt",
            agent_key="writer",
            dispatch_id="dispatch-interrupt",
            tool_call_id="tool-call-interrupt",
            request={"task": "write", "input": {}},
        )
        await repo.insert_message(
            session,
            session_id="parent-session",
            task_id="task-1",
            project_id="project-1",
            role="tool",
            status="complete",
            content='{"assistant_content": "Writer draft ready."}',
            tool_call_id="tool-call-interrupt",
            tool_name="dispatch_subagent",
        )

    emitted: list[tuple[str, dict[str, Any], str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            yield {
                "event": "on_chain_end",
                "data": {"output": {
                    "messages": [],
                    "iteration_count": 1,
                    "is_done": False,
                    "final_output": None,
                    "__interrupt__": [
                        type(
                            "Interrupt",
                            (),
                            {
                                "id": "approval-child-visible",
                                "value": {
                                    "type": "tool_approval",
                                    "approval_id": "approval-child-visible",
                                    "tool_name": "write_chapter",
                                    "tool_call_id": "tool-call-write",
                                    "message": "需要审批",
                                },
                            },
                        )()
                    ],
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [],
                "iteration_count": 1,
                "is_done": False,
                "final_output": None,
                "__interrupt__": [
                    type(
                        "Interrupt",
                        (),
                        {
                            "id": "approval-child-visible",
                            "value": {
                                "type": "tool_approval",
                                "approval_id": "approval-child-visible",
                                "tool_name": "write_chapter",
                                "tool_call_id": "tool-call-write",
                                "message": "需要审批",
                            },
                        },
                    )()
                ],
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.get_checkpointer",
        AsyncMock(return_value=object()),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    interrupted = await runner.run(row.id)

    assert interrupted["approval_request"]["approval_id"] == "approval-child-visible"
    child_interrupts = [
        payload
        for name, payload, room in emitted
        if name == "agent:interrupt"
        and room == "agent_subagent_session:child-thread-interrupt"
    ]
    assert len(child_interrupts) == 1
    assert child_interrupts[0]["session_id"] == "child-thread-interrupt"
    assert child_interrupts[0]["type"] == "tool_approval"
    assert child_interrupts[0]["approval_id"] == "approval-child-visible"
    assert child_interrupts[0]["tool_name"] == "write_chapter"
    assert child_interrupts[0]["tool_call_id"] == "tool-call-write"
    assert child_interrupts[0]["message"] == "需要审批"


@pytest.mark.asyncio
async def test_subagent_runner_emits_child_tool_result_for_tool_error_before_interrupt(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-tool-error",
            agent_key="composer",
            dispatch_id="dispatch-tool-error",
            tool_call_id="tool-call-dispatch",
            request={"task": "make a plan", "input": {}},
        )

    emitted: list[tuple[str, dict[str, Any], str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            yield {
                "event": "on_chain_start",
                "name": "composer",
                "tags": ["agent_node", "subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_start",
                "run_id": "child-run-approval",
                "tags": ["subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_end",
                "run_id": "child-run-approval",
                "tags": ["subagent_child"],
                "data": {
                    "output": AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "call-create-plan",
                                "name": "create_plan",
                                "args": {"value": "plan child beats"},
                            }
                        ],
                    ),
                },
            }
            yield {
                "event": "on_tool_start",
                "name": "create_plan",
                "run_id": "child-tool-approval",
                "tags": ["subagent_child"],
                "data": {"input": {"value": "plan child beats"}},
                "metadata": {"tool_call_id": "call-create-plan"},
            }
            yield {
                "event": "on_tool_error",
                "name": "create_plan",
                "run_id": "child-tool-approval",
                "tags": ["subagent_child"],
                "data": {
                    "input": {"value": "plan child beats"},
                    "error": RuntimeError("approval required"),
                },
                "metadata": {"tool_call_id": "call-create-plan"},
            }
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {
                    "output": {
                        "messages": [
                            AIMessage(
                                content="",
                                tool_calls=[
                                    {
                                        "id": "call-create-plan",
                                        "name": "create_plan",
                                        "args": {"value": "plan child beats"},
                                    }
                                ],
                            )
                        ],
                        "iteration_count": 1,
                        "is_done": False,
                        "final_output": None,
                        "__interrupt__": [
                            type(
                                "Interrupt",
                                (),
                                {
                                    "id": "approval-create-plan",
                                    "value": {
                                        "type": "tool_approval",
                                        "approval_id": "approval-create-plan",
                                        "tool_name": "create_plan",
                                        "tool_call_id": "call-create-plan",
                                        "message": "需要审批",
                                    },
                                },
                            )()
                        ],
                    }
                },
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [],
                "iteration_count": 1,
                "is_done": False,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.get_checkpointer",
        AsyncMock(return_value=object()),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    interrupted = await runner.run(row.id)

    assert interrupted["approval_request"]["approval_id"] == "approval-create-plan"
    child_tool_results = [
        payload
        for name, payload, room in emitted
        if name == "agent:tool_result"
        and room == "agent_subagent_session:child-thread-tool-error"
    ]
    assert len(child_tool_results) == 1
    assert child_tool_results[0]["session_id"] == "child-thread-tool-error"
    assert child_tool_results[0]["tool_call_id"] == "call-create-plan"
    assert child_tool_results[0]["tool"] == "create_plan"
    assert child_tool_results[0]["input"] == {"value": "plan child beats"}


@pytest.mark.asyncio
async def test_subagent_runner_emits_parent_subagent_status_without_mutating_dispatch_message(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-status",
            agent_key="writer",
            dispatch_id="dispatch-status",
            tool_call_id="tool-call-status",
            request={"task": "write", "input": {}},
        )
        await repo.insert_message(
            session,
            session_id="parent-session",
            task_id="task-1",
            project_id="project-1",
            role="tool",
            status="complete",
            content='{"assistant_content": "Writer draft ready."}',
            tool_call_id="tool-call-status",
            tool_name="dispatch_subagent",
        )

    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            yield {
                "event": "on_chain_end",
                "data": {"output": {
                    "messages": [AIMessage(content="writer finished")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="writer finished")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    await runner.run(row.id)

    assert any(
        item == (
            "agent:subagent_status",
            {
                "parent_session_id": "parent-session",
                "child_run_id": row.id,
                "child_thread_id": "child-thread-status",
                "agent_key": "writer",
                "agent_number": row.metadata_json["agent_number"],
                "status": "completed",
                "queued_messages": 0,
                "is_active": True,
                "pending_approval": None,
            },
            "agent_subagents:parent-session",
        )
        for item in emitted
    )
    assert emitted[-1][0] == "agent:done"
    assert emitted[-1][2] == "agent_subagent_session:child-thread-status"
    assert emitted[-1][1].get("session_id") == "child-thread-status"
    assert isinstance(emitted[-1][1].get("created_at"), str) and emitted[-1][1]["created_at"]
    assert not [
        payload
        for name, payload, room in emitted
        if name == "agent:tool_result"
        and room == "agent_session:parent-session"
        and payload.get("tool_call_id") == "tool-call-status"
    ]

    async with db_session_factory() as session:
        parent_messages = await repo.list_by_session(session, "parent-session")

    assert len(parent_messages) == 1
    assert parent_messages[0].role == "tool"
    assert parent_messages[0].content == '{"assistant_content": "Writer draft ready."}'
    assert parent_messages[0].tool_call_id == "tool-call-status"


@pytest.mark.asyncio
async def test_subagent_runner_streams_and_persists_child_transcript_on_child_thread(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-transcript",
            agent_key="writer",
            dispatch_id="dispatch-transcript",
            tool_call_id="tool-call-transcript",
            request={"task": "write child transcript", "input": {}},
        )

    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            assert version == "v2"
            assert config is not None
            assert config["configurable"]["thread_id"] == "child-thread-transcript"
            assert "subagent_child" in config["tags"]
            yield {
                "event": "on_chain_start",
                "name": "writer",
                "tags": ["agent_node", "subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_start",
                "run_id": "child-run-1",
                "tags": ["subagent_child"],
                "data": {},
            }
            yield {
                "event": "on_chat_model_stream",
                "run_id": "child-run-1",
                "tags": ["subagent_child"],
                "data": {"chunk": AIMessageChunk(content="child stream output")},
            }
            yield {
                "event": "on_chat_model_end",
                "run_id": "child-run-1",
                "tags": ["subagent_child"],
                "data": {"output": AIMessageChunk(content="child stream output")},
            }
            yield {
                "event": "on_tool_start",
                "name": "read_chapter",
                "run_id": "child-tool-1",
                "tags": ["subagent_child"],
                "data": {"input": {"order": 1}},
                "metadata": {"tool_call_id": "call-child-tool"},
            }
            yield {
                "event": "on_tool_end",
                "name": "read_chapter",
                "run_id": "child-tool-1",
                "tags": ["subagent_child"],
                "metadata": {"tool_call_id": "call-child-tool"},
                "data": {
                    "input": {"order": 1},
                    "output": "child tool output",
                },
            }
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="child stream output")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="child stream output")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    result = await runner.run(row.id)

    assert result["assistant_content"] == "child stream output"

    child_events = [
        (name, payload, room)
        for name, payload, room in emitted
        if payload.get("session_id") == "child-thread-transcript"
    ]
    assert child_events == [
        (
            "agent:token",
            {
                "session_id": "child-thread-transcript",
                "run_id": "child-run-1",
                "content": "child stream output",
            },
            "agent_subagent_session:child-thread-transcript",
        ),
        (
            "agent:tool_call",
            {
                "session_id": "child-thread-transcript",
                "run_id": "child-tool-1",
                "tool_call_id": "call-child-tool",
                "tool": "read_chapter",
                "input": {"order": 1},
            },
            "agent_subagent_session:child-thread-transcript",
        ),
        (
            "agent:tool_result",
            {
                "session_id": "child-thread-transcript",
                "run_id": "child-tool-1",
                "tool_call_id": "call-child-tool",
                "tool": "read_chapter",
                "input": {"order": 1},
                "output": "child tool output",
            },
            "agent_subagent_session:child-thread-transcript",
        ),
        (
            "agent:done",
            {
                "session_id": "child-thread-transcript",
                "created_at": child_events[-1][1]["created_at"],
            },
            "agent_subagent_session:child-thread-transcript",
        ),
    ]
    assert all(
        not (
            room == "agent_session:parent-session"
            and payload.get("session_id") == "child-thread-transcript"
        )
        for _, payload, room in emitted
    )

    async with db_session_factory() as session:
        child_messages = await repo.list_by_session(session, "child-thread-transcript")
        parent_messages = await repo.list_by_session(session, "parent-session")

    assert [message.role for message in child_messages] == ["assistant", "tool"]
    assert child_messages[0].content == "child stream output"
    assert child_messages[0].agent_id == "writer"
    assert child_messages[1].content == "child tool output"
    assert child_messages[1].tool_call_id == "call-child-tool"
    assert all(
        message.session_id != "child-thread-transcript" for message in parent_messages
    )


@pytest.mark.asyncio
async def test_subagent_runner_accumulates_parent_task_usage_and_persists_child_usage_snapshot(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-usage",
            agent_key="writer",
            dispatch_id="dispatch-usage",
            tool_call_id="tool-call-usage",
            request={"task": "track child usage", "input": {}},
        )

    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            yield {
                "event": "on_chat_model_end",
                "run_id": "child-run-usage",
                "tags": ["subagent_child"],
                "data": {
                        "output": AIMessage(
                            content="usage child output",
                            usage_metadata={
                                "input_tokens": 18,
                                "output_tokens": 7,
                                "total_tokens": 25,
                                "input_token_details": {"cache_read": 3},
                            },
                        )
                    },
                }
            yield {
                "event": "on_chain_end",
                "tags": ["subagent_child"],
                "data": {"output": {
                    "messages": [AIMessage(content="usage child output")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="usage child output")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    await runner.run(row.id)

    async with db_session_factory() as session:
        task = await session.get(Task, "task-1")
        child = await session.get(AgentChildRun, row.id)

    assert task is not None
    assert task.token_input == 18
    assert task.token_output == 7
    assert task.token_cache == 3
    assert task.context_input_tokens == 18
    assert child is not None
    assert child.metadata_json["token_usage"] == {
        "token_input": 18,
        "token_output": 7,
        "token_cache": 3,
        "context_input_tokens": 18,
        "context_length": 8000,
    }
    assert (
        "agent:task_usage_delta",
        {
            "session_id": "parent-session",
            "task_id": "task-1",
            "token_input": 18,
            "token_output": 7,
            "token_cache": 3,
        },
        "agent_session:parent-session",
    ) in emitted


@pytest.mark.asyncio
async def test_subagent_runner_does_not_emit_parent_dispatch_result_for_sync_completion(
    db_session_factory,
    monkeypatch,
):
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    async with db_session_factory() as session:
        row = await create_child_run(
            session,
            parent_session_id="parent-session",
            parent_task_id="task-1",
            parent_thread_id="parent-session",
            child_thread_id="child-thread-sync-status",
            agent_key="writer",
            dispatch_id="dispatch-sync-status",
            tool_call_id="tool-call-sync-status",
            request={"task": "write", "input": {}},
        )

    emitted: list[tuple[str, dict, str | None]] = []

    async def fake_emit(name, payload, room=None):
        emitted.append((name, payload, room))

    class FakeGraph:
        async def astream_events(self, initial_state, config=None, version=None):
            yield {
                "event": "on_chain_end",
                "data": {"output": {
                    "messages": [AIMessage(content="writer finished")],
                    "iteration_count": 1,
                    "is_done": True,
                    "final_output": None,
                }},
            }

        async def ainvoke(self, initial_state, config=None):
            return {
                "messages": [AIMessage(content="writer finished")],
                "iteration_count": 1,
                "is_done": True,
                "final_output": None,
            }

    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.emit", fake_emit)
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_chat_model",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner.create_react_agent",
        lambda *_args, **_kwargs: FakeGraph(),
    )

    runner = SubagentRunner(
        session_factory=db_session_factory,
        model_config={
            "provider_type": "openai",
            "base_url": "",
            "api_key": "key",
            "model_id": "gpt-test",
            "max_context_tokens": 8000,
        },
        project_id="project-1",
    )
    await runner.run(row.id)

    sync_status_events = [
        payload
        for name, payload, room in emitted
        if name == "agent:subagent_status"
        and room == "agent_subagents:parent-session"
        and payload.get("child_run_id") == row.id
    ]
    assert len(sync_status_events) >= 2
    assert (sync_status_events[0]["status"], sync_status_events[0]["queued_messages"]) == (
        "running",
        0,
    )
    assert (sync_status_events[-1]["status"], sync_status_events[-1]["queued_messages"]) == (
        "completed",
        0,
    )
    assert not [
        payload
        for name, payload, _room in emitted
        if name == "agent:tool_result"
        and payload.get("tool_call_id") == "tool-call-sync-status"
    ]
    assert [
        payload
        for name, payload, room in emitted
        if name == "agent:done"
        and room == "agent_subagent_session:child-thread-sync-status"
        and payload.get("session_id") == "child-thread-sync-status"
        and isinstance(payload.get("created_at"), str)
        and payload.get("created_at")
    ]
