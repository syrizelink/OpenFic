import asyncio
from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.agent_runtime.context.compaction.service import CompactionError
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.react_agent import create_react_agent, maybe_auto_compact
from app.agent_runtime.persistence.errors import PersistenceLoadError
from app.agent_runtime.types import ReactAgentConfig, TerminationCondition


class _NoopTool(BaseTool):
    name: str = "noop"
    description: str = "noop"

    def _run(self, **kwargs):  # pragma: no cover - sync path unused
        return "ok"

    async def _arun(self, **kwargs):
        return "ok"


def test_llm_call_uses_build_context_when_config_provided() -> None:
    config = ReactAgentConfig(
        name="writer",
        tools=[_NoopTool()],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=1,
    )

    fake_parts = [
        ContextMessage(role="system", content="sys", metadata={"part": "system"}),
        ContextMessage(role="user", content="hi", metadata={"part": "history", "seq": 1}),
    ]
    fallback_messages = [SystemMessage(content="sys"), HumanMessage(content="hi")]
    fake_response = AIMessage(content="done")

    async def _mock_invoke(*args, **kwargs):
        return fake_response

    with (
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=fallback_messages),
        ),
        patch(
            "app.agent_runtime.graph.react_agent.build_context_parts",
            new=AsyncMock(return_value=fake_parts),
            create=True,
        ) as mocked_build_parts,
        patch(
            "app.agent_runtime.graph.react_agent._invoke_model",
            side_effect=_mock_invoke,
        ) as mocked_invoke,
    ):
        model = Mock()
        model.bind_tools.return_value = model
        graph = create_react_agent(config, model=model)
        runtime_state: dict[str, object] = {
            "session_id": "s1",
            "task_id": "t1",
            "project_id": "p1",
            "model_config": {"max_context_tokens": 8000},
            "active_agent": "writer",
            "is_completed": False,
            "error": None,
            "retry_count": 0,
            "message_checkpoints": [],
            "user_request": "hi",
            "installed_skill_ids": [],
        }
        runtime_context = {"transient_context_key": "v2"}
        cfg = {
            "configurable": {
                "runtime_state": runtime_state,
                "runtime_context": runtime_context,
                "db_session": AsyncMock(),
                "thread_id": "t1",
            }
        }
        initial = {
            "messages": [HumanMessage(content="hi")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        }
        asyncio.run(graph.ainvoke(initial, config=cfg))

    mocked_build_parts.assert_awaited_once()
    mocked_invoke.assert_awaited_once()
    await_args = mocked_build_parts.await_args
    assert await_args is not None
    _, kwargs = await_args
    assert kwargs["agent_name"] == "writer"
    assert kwargs["state"]["transient_context_key"] == "v2"
    assert "transient_context_key" not in runtime_state


async def _noop_event_sink(_name: str, _payload: dict) -> None:
    return None


async def _noop_usage_sink(_payload: dict) -> None:
    return None


def _auto_compaction_state() -> dict[str, object]:
    return {
        "session_id": "s1",
        "task_id": "t1",
        "project_id": "p1",
        "model_config": {"max_context_tokens": 10},
        "active_agent": "writer",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "hi",
        "installed_skill_ids": [],
    }


def _compaction_parts() -> list[ContextMessage]:
    return [
        ContextMessage(role="system", content="static", metadata={"part": "system"}),
        ContextMessage(role="user", content="history user", metadata={"part": "history", "seq": 1}),
        ContextMessage(role="assistant", content="history assistant", metadata={"part": "history", "seq": 2}),
    ]


@pytest.mark.asyncio
async def test_auto_compaction_emits_stable_error_when_compaction_load_fails() -> None:
    events: list[tuple[str, dict]] = []

    async def event_sink(name: str, payload: dict) -> None:
        events.append((name, payload))

    with (
        patch(
            "app.agent_runtime.graph.react_agent.count_context_tokens",
            return_value=9,
        ),
        patch(
            "app.agent_runtime.graph.react_agent.compaction_repo.list_by_session",
            side_effect=PersistenceLoadError("raw database details"),
        ),
    ):
        with pytest.raises(CompactionError) as exc_info:
            await maybe_auto_compact(
                state=_auto_compaction_state(),
                agent_name="writer",
                parts=_compaction_parts(),
                db_session=AsyncMock(),
                event_sink=event_sink,
                usage_sink=_noop_usage_sink,
            )

    assert exc_info.value.code == "compaction_load_failed"
    assert "raw database details" not in exc_info.value.message
    assert events == [
        (
            "agent:compaction_error",
            {
                "session_id": "s1",
                "task_id": "t1",
                "trigger": "auto",
                "code": "compaction_load_failed",
                "message": "压缩状态加载失败，当前请求已中止",
            },
        )
    ]


@pytest.mark.asyncio
async def test_auto_compaction_wraps_unhandled_compact_window_error() -> None:
    events: list[tuple[str, dict]] = []
    window = SimpleNamespace(
        start_seq=1,
        end_seq=2,
        messages=_compaction_parts()[1:],
        source_input_tokens=9,
        transcript="history transcript",
    )

    async def event_sink(name: str, payload: dict) -> None:
        events.append((name, payload))

    with (
        patch(
            "app.agent_runtime.graph.react_agent.count_context_tokens",
            return_value=9,
        ),
        patch(
            "app.agent_runtime.graph.react_agent.compaction_repo.list_by_session",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agent_runtime.graph.react_agent.select_compaction_window",
            return_value=window,
        ),
        patch(
            "app.agent_runtime.graph.react_agent.compact_window",
            new=AsyncMock(side_effect=RuntimeError("raw upstream details")),
        ),
    ):
        with pytest.raises(CompactionError) as exc_info:
            await maybe_auto_compact(
                state=_auto_compaction_state(),
                agent_name="writer",
                parts=_compaction_parts(),
                db_session=AsyncMock(),
                event_sink=event_sink,
                usage_sink=_noop_usage_sink,
            )

    assert exc_info.value.code == "llm_error"
    assert exc_info.value.message == "压缩失败，当前请求已中止"
    assert events == [
        (
            "agent:compaction_error",
            {
                "session_id": "s1",
                "task_id": "t1",
                "trigger": "auto",
                "code": "llm_error",
                "message": "压缩失败，当前请求已中止",
            },
        )
    ]


def test_auto_compaction_runs_before_main_model_and_rebuilds_context() -> None:
    config = ReactAgentConfig(
        name="writer",
        tools=[_NoopTool()],
        termination=TerminationCondition(mode="tool_success", tool_name="noop"),
        max_iterations=3,
    )
    injected_queue: asyncio.Queue[tuple[str | None, str, str]] = asyncio.Queue()
    injected_queue.put_nowait(("msg_pending_1", "user", "补充要求"))
    consume_sink = AsyncMock(return_value=True)
    first_parts = [
        ContextMessage(role="system", content="static", metadata={"part": "system"}),
        ContextMessage(role="user", content="history user", metadata={"part": "history", "seq": 1}),
        ContextMessage(role="assistant", content="history assistant", metadata={"part": "history", "seq": 2}),
        ContextMessage(role="system", content="old summary", metadata={"part": "compaction_summary"}),
    ]
    rebuilt_parts = [
        ContextMessage(role="system", content="static rebuilt", metadata={"part": "system"}),
        ContextMessage(role="user", content="post-summary history", metadata={"part": "history", "seq": 3}),
    ]
    build_calls = deque([first_parts, rebuilt_parts])
    counted_candidates: list[list[str]] = []
    selected_history: list[ContextMessage] = []
    model_messages: list[HumanMessage | SystemMessage | AIMessage] = []

    async def fake_build_context_parts(**_kwargs):
        return build_calls.popleft()

    def fake_count_context_tokens(parts):
        contents = [part.content for part in parts]
        counted_candidates.append(contents)
        has_runtime_messages = (
            "补充要求" in contents
            and any("Call the `noop` tool" in content for content in contents)
        )
        return 9 if has_runtime_messages else 0

    def fake_select_compaction_window(history, _compactions, max_context_tokens):
        selected_history.extend(history)
        assert max_context_tokens == 10
        return SimpleNamespace(
            start_seq=1,
            end_seq=2,
            messages=list(history),
            source_input_tokens=9,
            transcript="history transcript",
        )

    async def fake_compact_window(*_args, **kwargs):
        assert kwargs["trigger"] == "auto"
        assert callable(kwargs["event_sink"])
        assert kwargs["usage_sink"] is _noop_usage_sink
        return SimpleNamespace(id="compaction-1")

    async def fake_list_by_session(_db_session, session_id):
        assert session_id == "s1"
        return []

    async def _mock_invoke(_model, messages):
        model_messages.extend(messages)
        return AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "noop", "args": {}}],
        )

    with (
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=[HumanMessage(content="fallback")]),
        ),
        patch(
            "app.agent_runtime.graph.react_agent.build_context_parts",
            new=AsyncMock(side_effect=fake_build_context_parts),
            create=True,
        ) as mocked_build_parts,
        patch(
            "app.agent_runtime.graph.react_agent.count_context_tokens",
            side_effect=fake_count_context_tokens,
            create=True,
        ),
        patch(
            "app.agent_runtime.graph.react_agent.select_compaction_window",
            side_effect=fake_select_compaction_window,
            create=True,
        ) as mocked_select,
        patch(
            "app.agent_runtime.graph.react_agent.compact_window",
            side_effect=fake_compact_window,
            create=True,
        ) as mocked_compact,
        patch(
            "app.agent_runtime.graph.react_agent.compaction_repo.list_by_session",
            side_effect=fake_list_by_session,
            create=True,
        ),
        patch(
            "app.agent_runtime.graph.react_agent._invoke_model",
            side_effect=_mock_invoke,
        ),
    ):
        model = Mock()
        model.bind_tools.return_value = model
        graph = create_react_agent(config, model=model, inject_queue=injected_queue)
        asyncio.run(
            graph.ainvoke(
                {
                    "messages": [
                        HumanMessage(content="hi"),
                        AIMessage(content="plain answer"),
                    ],
                    "iteration_count": 1,
                    "is_done": False,
                    "final_output": None,
                },
                config={
                    "configurable": {
                        "runtime_state": {
                            "session_id": "s1",
                            "task_id": "t1",
                            "project_id": "p1",
                            "model_config": {"max_context_tokens": 10},
                            "active_agent": "writer",
                            "is_completed": False,
                            "error": None,
                            "retry_count": 0,
                            "message_checkpoints": [],
                            "user_request": "hi",
                            "installed_skill_ids": [],
                        },
                        "db_session": AsyncMock(),
                        "thread_id": "s1",
                        "agent_event_sink": _noop_event_sink,
                        "compaction_usage_sink": _noop_usage_sink,
                        "inject_message_consumed_sink": consume_sink,
                    }
                },
            )
        )

    assert mocked_build_parts.await_count == 2
    assert counted_candidates == [[
        "static",
        "history user",
        "history assistant",
        "old summary",
        "补充要求",
        "Call the `noop` tool to finish this step. Do not answer in plain text.",
    ]]
    mocked_select.assert_called_once()
    assert [part.content for part in selected_history] == [
        "history user",
        "history assistant",
    ]
    mocked_compact.assert_awaited_once()
    consume_sink.assert_awaited_once_with("msg_pending_1")
    assert [message.content for message in model_messages if isinstance(message, HumanMessage)] == [
        "post-summary history",
        "补充要求",
        "Call the `noop` tool to finish this step. Do not answer in plain text.",
    ]


def test_auto_compaction_stays_silent_below_threshold() -> None:
    config = ReactAgentConfig(
        name="writer",
        tools=[_NoopTool()],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=1,
    )
    events: list[tuple[str, dict]] = []
    parts = [
        ContextMessage(role="system", content="static", metadata={"part": "system"}),
        ContextMessage(role="user", content="short history", metadata={"part": "history", "seq": 1}),
    ]

    async def event_sink(name: str, payload: dict) -> None:
        events.append((name, payload))

    async def _mock_invoke(_model, _messages):
        return AIMessage(content="done")

    with (
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=[HumanMessage(content="fallback")]),
        ),
        patch(
            "app.agent_runtime.graph.react_agent.build_context_parts",
            new=AsyncMock(return_value=parts),
            create=True,
        ),
        patch(
            "app.agent_runtime.graph.react_agent.count_context_tokens",
            return_value=7,
            create=True,
        ),
        patch(
            "app.agent_runtime.graph.react_agent.compact_window",
            new=AsyncMock(),
            create=True,
        ) as mocked_compact,
        patch(
            "app.agent_runtime.graph.react_agent._invoke_model",
            side_effect=_mock_invoke,
        ) as mocked_invoke,
    ):
        model = Mock()
        model.bind_tools.return_value = model
        graph = create_react_agent(config, model=model)
        asyncio.run(
            graph.ainvoke(
                {
                    "messages": [HumanMessage(content="hi")],
                    "iteration_count": 0,
                    "is_done": False,
                    "final_output": None,
                },
                config={
                    "configurable": {
                        "runtime_state": {
                            "session_id": "s1",
                            "task_id": "t1",
                            "project_id": "p1",
                            "model_config": {"max_context_tokens": 10},
                            "active_agent": "writer",
                            "is_completed": False,
                            "error": None,
                            "retry_count": 0,
                            "message_checkpoints": [],
                            "user_request": "hi",
                            "installed_skill_ids": [],
                        },
                        "db_session": AsyncMock(),
                        "thread_id": "s1",
                        "agent_event_sink": event_sink,
                        "compaction_usage_sink": _noop_usage_sink,
                    }
                },
            )
        )

    mocked_compact.assert_not_awaited()
    mocked_invoke.assert_awaited_once()
    assert events == []


def test_llm_call_marks_consumed_injected_user_messages_sent() -> None:
    config = ReactAgentConfig(
        name="writer",
        tools=[_NoopTool()],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=1,
    )

    injected_queue: asyncio.Queue[tuple[str | None, str, str]] = asyncio.Queue()
    injected_queue.put_nowait(("msg_pending_1", "user", "补充要求"))
    consume_sink = AsyncMock()
    observed_messages: list[HumanMessage | SystemMessage | AIMessage] = []

    async def _mock_invoke(_model, messages):
        observed_messages.extend(messages)
        return AIMessage(content="done")

    with patch(
        "app.agent_runtime.graph.react_agent._invoke_model",
        side_effect=_mock_invoke,
    ):
        model = Mock()
        model.bind_tools.return_value = model
        graph = create_react_agent(config, model=model, inject_queue=injected_queue)
        initial = {
            "messages": [HumanMessage(content="hi")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        }
        asyncio.run(
            graph.ainvoke(
                initial,
                config={
                    "configurable": {
                        "inject_message_consumed_sink": consume_sink,
                    }
                },
            )
        )

    consume_sink.assert_awaited_once_with("msg_pending_1")
    assert any(
        isinstance(message, HumanMessage) and message.content == "补充要求"
        for message in observed_messages
    )


def test_to_history_dict_preserves_reasoning_content() -> None:
    from app.agent_runtime.graph.react_agent import _to_history_dict

    message = AIMessage(
        content="",
        additional_kwargs={"reasoning_content": "先分析"},
        tool_calls=[{"id": "call_1", "name": "noop", "args": {}}],
    )

    out = _to_history_dict(message)

    assert out["additional_kwargs"] == {"reasoning_content": "先分析"}
    assert out["tool_calls"][0]["id"] == "call_1"
    assert out["tool_calls"][0]["name"] == "noop"
    assert out["tool_calls"][0]["args"] == {}


def test_to_history_dict_uses_response_metadata_reasoning_content() -> None:
    from app.agent_runtime.graph.react_agent import _to_history_dict

    message = AIMessage(
        content="",
        response_metadata={"reasoning_content": "从 metadata 来的思考"},
    )

    out = _to_history_dict(message)

    assert out["additional_kwargs"] == {"reasoning_content": "从 metadata 来的思考"}


def test_to_history_dict_uses_openfic_response_metadata_for_internal_history_fields() -> None:
    from app.agent_runtime.graph.react_agent import _to_history_dict

    human = HumanMessage(
        content="hi",
        response_metadata={"openfic_seq": 7},
    )
    tool = ToolMessage(
        content="result",
        tool_call_id="call_1",
        response_metadata={
            "openfic_seq": 8,
            "openfic_tool_name": "read_chapter",
        },
    )

    human_out = _to_history_dict(human)
    tool_out = _to_history_dict(tool)

    assert human_out["metadata"] == {"part": "history", "seq": 7}
    assert tool_out["metadata"] == {
        "part": "history",
        "seq": 8,
        "tool_name": "read_chapter",
    }
    assert tool_out["name"] == "read_chapter"


class _QueueFollowUpTool(BaseTool):
    name: str = "submit_result"
    description: str = "submit"

    queue: asyncio.Queue | None = None
    should_queue: bool = True

    def _run(self, **kwargs):  # pragma: no cover - sync path unused
        raise NotImplementedError

    async def _arun(self, **kwargs):
        assert self.queue is not None
        if self.should_queue:
            await self.queue.put(("msg_pending_1", "user", "补充要求"))
            self.should_queue = False
        return "ok"


def test_tool_success_path_continues_with_pending_follow_up_before_ending() -> None:
    injected_queue: asyncio.Queue[tuple[str | None, str, str]] = asyncio.Queue()
    follow_up_tool = _QueueFollowUpTool()
    follow_up_tool.queue = injected_queue
    config = ReactAgentConfig(
        name="writer",
        tools=[follow_up_tool],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
        max_iterations=4,
    )

    consume_sink = AsyncMock(return_value=True)
    observed_human_contents: deque[list[str]] = deque()
    responses = deque([
        AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "submit_result", "args": {"result": "done"}}],
        ),
        AIMessage(
            content="",
            tool_calls=[{"id": "call_2", "name": "submit_result", "args": {"result": "follow-up"}}],
        ),
    ])

    async def _mock_invoke(_model, messages):
        observed_human_contents.append(
            [
                message.content
                for message in messages
                if isinstance(message, HumanMessage)
            ]
        )
        return responses.popleft()

    with patch(
        "app.agent_runtime.graph.react_agent._invoke_model",
        side_effect=_mock_invoke,
    ):
        model = Mock()
        model.bind_tools.return_value = model
        graph = create_react_agent(config, model=model, inject_queue=injected_queue)
        result = asyncio.run(
            graph.ainvoke(
                {
                    "messages": [HumanMessage(content="hi")],
                    "iteration_count": 0,
                    "is_done": False,
                    "final_output": None,
                },
                config={
                    "configurable": {
                        "inject_message_consumed_sink": consume_sink,
                    }
                },
            )
        )

    assert result["is_done"] is True
    assert len(observed_human_contents) == 2
    assert observed_human_contents[0] == ["hi"]
    assert observed_human_contents[1] == ["hi", "补充要求"]
    consume_sink.assert_awaited_once_with("msg_pending_1")
