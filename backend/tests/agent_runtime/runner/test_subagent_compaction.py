from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import HumanMessage

from app.agent_runtime.context.compaction.overlay import apply_compaction_overlay
from app.agent_runtime.context.compaction.window import select_compaction_window
from app.agent_runtime.context.parts.history import build_history
from app.agent_runtime.context.pruning import OLD_TOOL_OUTPUT_PLACEHOLDER
from app.agent_runtime.graph.react_agent import _to_history_dict
from app.agent_runtime.persistence.compaction_types import PersistedCompaction
from app.agent_runtime.persistence.model import AgentRunMessage
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence.repo import _row_to_dto
from app.agent_runtime.runner.subagent_runner import (
    SubagentRunner,
    _annotate_child_history,
    build_child_messages,
)


def persisted(seq, role, content, **kwargs):
    return _row_to_dto(
        AgentRunMessage(
            session_id="child",
            task_id="task",
            project_id="project",
            seq=seq,
            role=role,
            content=content,
            status="complete",
            **kwargs,
        )
    )


def test_sequence_annotation_keeps_uncommitted_results_and_pruned_content():
    messages = [
        {"role": "user", "content": "request", "metadata": {"seq": 0}},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "a", "name": "read", "args": {}},
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "a",
            "content": OLD_TOOL_OUTPUT_PLACEHOLDER,
            "metadata": {"pruned": True},
        },
        {"role": "tool", "tool_call_id": "not-committed", "content": "latest"},
    ]
    rows = [
        persisted(0, "user", "request", message_type="user_request"),
        persisted(1, "assistant", "", tool_calls='[{"id":"a"}]'),
        persisted(2, "tool", "original large body", tool_call_id="a"),
    ]
    _annotate_child_history(messages, rows)

    assert len(messages) == 4
    assert messages[1]["metadata"]["seq"] == 1
    assert messages[2]["metadata"] == {"seq": 2, "pruned": True}
    assert messages[2]["content"] == OLD_TOOL_OUTPUT_PLACEHOLDER
    assert messages[3]["content"] == "latest"
    assert "seq" not in messages[3]["metadata"]


@pytest.mark.asyncio
async def test_sequenced_child_history_compacts_and_keeps_live_tail():
    messages = [
        {"role": "user", "content": "request", "metadata": {"seq": 0}},
        {"role": "assistant", "content": "old output " * 100},
        {"role": "assistant", "content": "recent output"},
        {"role": "assistant", "content": "not committed yet"},
    ]
    rows = [
        persisted(1, "assistant", messages[1]["content"]),
        persisted(2, "assistant", messages[2]["content"]),
    ]
    _annotate_child_history(messages, rows)
    history = await build_history(messages)
    window = select_compaction_window(
        history,
        [],
        1000,
        tail_token_budget=1,
        min_compactable_tokens=1,
    )
    assert (window.start_seq, window.end_seq) == (1, 1)
    compaction = PersistedCompaction(
        id="cmp",
        session_id="child",
        task_id="task",
        project_id="project",
        start_seq=1,
        end_seq=1,
        summary="summary",
        trigger="auto",
        source_input_tokens=window.source_input_tokens,
        summary_tokens=1,
        created_at=datetime.now(UTC),
    )
    # A later LLM call annotates the same graph messages again; overlay must
    # continue hiding the compacted body while preserving the uncommitted tail.
    _annotate_child_history(messages, rows)
    overlaid = apply_compaction_overlay(await build_history(messages), [compaction])
    assert [part.content for part in overlaid] == [
        "request",
        "<compaction-summary>\nsummary\n</compaction-summary>",
        "recent output",
        "not committed yet",
    ]


def test_current_persisted_request_is_included_once():
    request = HumanMessage(content="request", response_metadata={"openfic_seq": 4})
    history = [request]
    assert build_child_messages(history, content="request", request_seq=4) == history
    assert len(build_child_messages([], content="legacy request")) == 1


@pytest.mark.asyncio
async def test_notify_replaces_checkpoint_history_and_keeps_compacted_body_hidden(
    monkeypatch,
):
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import MemorySaver
    from app.agent_runtime.context.settings import ContextSettings
    from app.agent_runtime.graph.react_agent import create_react_agent
    from app.agent_runtime.types import ReactAgentConfig, TerminationCondition

    old_body = "old output " * 100
    history = [
        HumanMessage(content="request", response_metadata={"openfic_seq": 0}),
        AIMessage(content=old_body, response_metadata={"openfic_seq": 1}),
        AIMessage(content="recent output", response_metadata={"openfic_seq": 2}),
    ]
    compaction = PersistedCompaction(
        id="cmp", session_id="child", task_id="task", project_id="project",
        start_seq=1, end_seq=1, summary="summary", trigger="auto",
        source_input_tokens=1000, summary_tokens=1, created_at=datetime.now(UTC),
    )
    captured = []

    async def build_parts(**kwargs):
        return apply_compaction_overlay(
            await build_history(kwargs["node_messages"]), [compaction]
        )

    async def invoke(_model, messages, **kwargs):
        captured.append([message.content for message in messages])
        return AIMessage(content="done")

    prefix = "app.agent_runtime.graph.react_agent."
    monkeypatch.setattr(prefix + "build_context_parts", build_parts)
    monkeypatch.setattr(prefix + "maybe_auto_compact", AsyncMock(return_value=False))
    monkeypatch.setattr(
        prefix + "load_context_settings", AsyncMock(return_value=ContextSettings())
    )
    monkeypatch.setattr(prefix + "_invoke_model", invoke)
    graph = create_react_agent(
        ReactAgentConfig(
            name="writer", tools=[],
            termination=TerminationCondition(mode="no_tool_call"),
        ),
        model=Mock(), checkpointer=MemorySaver(),
    )
    runtime_state = {
        "session_id": "child", "model_config": {"max_context_tokens": 10000},
    }
    config = {"configurable": {
        "thread_id": "child", "runtime_state": runtime_state,
        "db_session": AsyncMock(),
    }}
    # Seed a real checkpoint containing the original, uncompressed messages.
    await graph.ainvoke({"messages": list(history), "iteration_count": 0}, config)

    runner = SubagentRunner(session_factory=Mock(), model_config={}, project_id="project")
    row = SimpleNamespace(
        id="run", child_thread_id="child", parent_task_id="task",
        parent_session_id="parent", agent_key="writer",
    )
    monkeypatch.setattr(runner, "_load_agent_definition", AsyncMock())
    monkeypatch.setattr(runner, "_load_history", AsyncMock(side_effect=lambda *_: list(history)))
    monkeypatch.setattr(runner, "_build_runtime_state", AsyncMock(return_value=runtime_state))
    monkeypatch.setattr(runner, "_build_graph", AsyncMock(return_value=(graph, {})))
    monkeypatch.setattr(runner, "_complete_request", AsyncMock(return_value=row))
    monkeypatch.setattr(runner, "_publish_parent_subagent_status_row", AsyncMock())

    async def invoke_graph(_row, _graph, _model_config, graph_input, *_args):
        return await _graph.ainvoke(graph_input, config)

    monkeypatch.setattr(runner, "_invoke_graph", invoke_graph)
    for seq in (4, 6):
        history.extend([
            AIMessage(content="done", response_metadata={"openfic_seq": seq - 1}),
            HumanMessage(content=f"notify-{seq}", response_metadata={"openfic_seq": seq}),
        ])
        request = SimpleNamespace(
            id=f"request-{seq}", content=f"notify-{seq}",
            child_user_message_seq=seq, parent_revision_id=None, request_kind="notify",
        )
        result = await runner._run_request(row, request)
        assert result["assistant_content"] == "done"
        assert captured[-1] == [
            "request", "<compaction-summary>\nsummary\n</compaction-summary>",
            *[message.content for message in history[2:]],
        ]
        snapshot = await graph.aget_state(config)
        assert len(snapshot.values["messages"]) == len(history) + 1


def test_parallel_tool_completion_order_does_not_lose_sequence_numbers():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "a"},
                {"id": "b"},
            ],
        },
        {"role": "tool", "tool_call_id": "a", "content": "first"},
        {"role": "tool", "tool_call_id": "b", "content": "second"},
    ]
    _annotate_child_history(
        messages,
        [
            persisted(1, "assistant", "", tool_calls='[{"id":"a"},{"id":"b"}]'),
            persisted(2, "tool", "second", tool_call_id="b"),
            persisted(3, "tool", "first", tool_call_id="a"),
        ],
    )
    assert [message["metadata"]["seq"] for message in messages] == [1, 3, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [True, False])
async def test_overwritten_child_history_survives_checkpoint_approval_resume(
    monkeypatch, approved,
):
    from langchain_core.messages import AIMessage
    from langchain_core.tools import StructuredTool
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command, Overwrite, interrupt
    from app.agent_runtime.graph.react_agent import create_react_agent
    from app.agent_runtime.types import ReactAgentConfig, TerminationCondition

    async def approval() -> str:
        response = interrupt({"type": "tool_approval"})
        return "approved" if response["approved"] else "denied"

    tool = StructuredTool.from_function(
        coroutine=approval, name="approval", description="Request approval"
    )
    responses = iter([
        AIMessage(content="", tool_calls=[{
            "id": "call", "name": "approval", "args": {},
        }]),
        AIMessage(content="done"),
    ])

    async def invoke(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr("app.agent_runtime.graph.react_agent._invoke_model", invoke)
    graph = create_react_agent(
        ReactAgentConfig(
            name="writer", tools=[tool],
            termination=TerminationCondition(mode="no_tool_call"),
        ),
        model=Mock(), checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "child-approval"}}
    paused = await graph.ainvoke({
        "messages": Overwrite([HumanMessage(content="task")]), "iteration_count": 0,
    }, config)
    assert paused["__interrupt__"]

    resumed = await graph.ainvoke(Command(resume={"approved": approved}), config)
    assert [(message.type, message.content) for message in resumed["messages"]] == [
        ("human", "task"), ("ai", ""),
        ("tool", "approved" if approved else "denied"), ("ai", "done"),
    ]


@pytest.mark.asyncio
async def test_child_history_excludes_queued_requests_and_restores_prune_markers(
    monkeypatch,
):
    from langchain_core.messages import ToolMessage

    session = AsyncMock()
    runner = SubagentRunner(
        session_factory=lambda: session,
        model_config={},
        project_id="project",
    )
    monkeypatch.setattr(
        "app.agent_runtime.runner.subagent_runner._pending_child_message_ids",
        AsyncMock(return_value={"queued-request"}),
    )
    load = AsyncMock(
        return_value=[
            ToolMessage(
                content="original body",
                tool_call_id="a",
                response_metadata={"openfic_seq": 2, "openfic_pruned": True},
            ),
        ]
    )
    monkeypatch.setattr("app.agent_runtime.runner.subagent_runner.load_history", load)
    history = await runner._load_history("child")
    load.assert_awaited_once_with(
        session,
        "child",
        include_user_requests=True,
        exclude_message_ids={"queued-request"},
    )
    assert _to_history_dict(history[0])["content"] == OLD_TOOL_OUTPUT_PLACEHOLDER


@pytest.mark.asyncio
async def test_queued_request_is_excluded_before_pairing_tool_results():
    def row(seq, role, content, **kwargs):
        return AgentRunMessage(
            session_id="child",
            task_id="task",
            project_id="project",
            seq=seq,
            role=role,
            content=content,
            status="sent",
            **kwargs,
        )

    result = Mock()
    result.scalars.return_value.all.return_value = [
        row(0, "user", "current", message_type="user_request"),
        row(1, "assistant", "", tool_calls='[{"id":"a","name":"read","args":{}}]'),
        row(2, "user", "future", id="queued", message_type="user_request"),
        row(3, "tool", "result", tool_call_id="a", tool_name="read"),
    ]
    session = AsyncMock()
    session.execute.return_value = result
    messages = await load_history(
        session,
        "child",
        include_user_requests=True,
        exclude_message_ids={"queued"},
    )
    assert [message.content for message in messages] == ["current", "", "result"]
    assert messages[1].tool_calls[0]["id"] == messages[2].tool_call_id == "a"


@pytest.mark.asyncio
async def test_child_graph_auto_compacts_without_discarding_live_messages(monkeypatch):
    from langchain_core.messages import AIMessage
    from app.agent_runtime.graph.react_agent import create_react_agent
    from app.agent_runtime.context.settings import ContextSettings
    from app.agent_runtime.types import ReactAgentConfig, TerminationCondition

    original = [
        HumanMessage(content="request", response_metadata={"openfic_seq": 0}),
        AIMessage(content="old output " * 100),
        AIMessage(content="recent output"),
        AIMessage(content="not committed yet"),
    ]
    persisted_rows = [
        persisted(1, "assistant", original[1].content),
        persisted(2, "assistant", original[2].content),
    ]
    compactions = []
    captured = []

    async def resolve(messages):
        _annotate_child_history(messages, persisted_rows)

    async def build_parts(**kwargs):
        return apply_compaction_overlay(
            await build_history(kwargs["node_messages"]),
            compactions,
        )

    async def compact(_session, **kwargs):
        window = kwargs["window"]
        assert (window.start_seq, window.end_seq) == (1, 1)
        assert kwargs["model_config"] == {"max_context_tokens": 1000}
        compactions.append(
            PersistedCompaction(
                id="cmp",
                session_id="child",
                task_id="task",
                project_id="project",
                start_seq=1,
                end_seq=1,
                summary="summary",
                trigger="auto",
                source_input_tokens=window.source_input_tokens,
                summary_tokens=1,
                created_at=datetime.now(UTC),
            )
        )

    async def invoke(_model, messages, **kwargs):
        captured.append([message.content for message in messages])
        return AIMessage(content="done")

    prefix = "app.agent_runtime.graph.react_agent."
    monkeypatch.setattr(prefix + "build_context_parts", build_parts)
    monkeypatch.setattr(prefix + "compact_window", compact)
    monkeypatch.setattr(prefix + "_invoke_model", invoke)
    monkeypatch.setattr(
        prefix + "compaction_repo.list_by_session",
        AsyncMock(
            side_effect=lambda *_args: list(compactions),
        ),
    )
    monkeypatch.setattr(
        prefix + "load_context_settings",
        AsyncMock(
            return_value=ContextSettings(
                compaction_trigger_ratio=0.1,
                compaction_tail_token_budget=1,
                compaction_min_compactable_tokens=1,
            )
        ),
    )
    graph = create_react_agent(
        ReactAgentConfig(
            name="writer",
            tools=[],
            max_iterations=1,
            termination=TerminationCondition(mode="no_tool_call"),
        ),
        model=Mock(),
    )
    config = {
        "configurable": {
            "runtime_state": {
                "session_id": "child",
                "model_config": {"max_context_tokens": 1000},
            },
            "model_config": {"max_context_tokens": 1000},
            "db_session": AsyncMock(),
            "history_seq_resolver": resolve,
        }
    }
    for _ in range(2):
        await graph.ainvoke({"messages": original, "iteration_count": 0}, config=config)

    assert len(compactions) == 1
    assert (
        captured
        == [
            [
                "request",
                "<compaction-summary>\nsummary\n</compaction-summary>",
                "recent output",
                "not committed yet",
            ]
        ]
        * 2
    )


@pytest.mark.asyncio
async def test_existing_child_history_uses_request_status_in_database():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlmodel import SQLModel
    from app.agent_runtime.persistence.model import AgentChildRun, AgentChildRunRequest

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AgentRunMessage.__table__,
            AgentChildRun.__table__,
            AgentChildRunRequest.__table__,
        ],
    )
    try:
        with Session(engine) as session:
            session.add(
                AgentChildRun(
                    id="run",
                    parent_session_id="parent",
                    parent_task_id="task",
                    parent_thread_id="parent",
                    child_thread_id="child",
                    agent_key="writer",
                    dispatch_id="dispatch",
                    tool_call_id="dispatch-call",
                )
            )
            for index, status in enumerate(["completed", "running", "pending"]):
                message_id = f"user-{index}"
                session.add(
                    AgentChildRunRequest(
                        child_run_id="run",
                        parent_session_id="parent",
                        parent_task_id="task",
                        request_kind="notify",
                        content=status,
                        status=status,
                        seq=index,
                        child_user_message_id=message_id,
                        child_user_message_seq=index,
                    )
                )
                session.add(
                    AgentRunMessage(
                        id=message_id,
                        session_id="child",
                        task_id="task",
                        project_id="project",
                        seq=index,
                        role="user",
                        content=status,
                        status="sent",
                        message_type="user_request",
                    )
                )
            session.commit()

            # Real SQLite queries through an async read interface, avoiding
            # this environment's hanging aiosqlite fixture.
            class Reader:
                async def execute(self, statement):
                    return session.execute(statement)

                async def close(self):
                    pass

            runner = SubagentRunner(
                session_factory=Reader,
                model_config={},
                project_id="project",
            )
            assert await load_history(Reader(), "child") == []
            history = await runner._load_history("child")
            messages = build_child_messages(history, content="running", request_seq=1)
            assert [message.content for message in messages] == ["completed", "running"]
            assert [
                message.response_metadata["openfic_seq"] for message in messages
            ] == [0, 1]
    finally:
        engine.dispose()
