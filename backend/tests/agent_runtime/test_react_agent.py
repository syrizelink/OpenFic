import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.tool import invalid_tool_call
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from app.agent_runtime.tools.base import AgentTool, HookResult
from app.agent_runtime.types import TerminationCondition, ReactAgentConfig
from app.agent_runtime.graph.react_agent import create_react_agent, ReactState, _invoke_tool


def _submit_result(result: str) -> str:
    return f"submitted: {result}"


def _add_numbers(a: int, b: int) -> int:
    return a + b


async def _async_submit_result(result: str) -> str:
    return _submit_result(result)


async def _async_add_numbers(a: int, b: int) -> int:
    return _add_numbers(a, b)


def _create_plan_tool(executed_calls: list[dict[str, object]]) -> StructuredTool:
    async def _async_create_plan(
        topic: str,
        description: str,
        todos: list[dict[str, str]],
    ) -> str:
        executed_calls.append(
            {
                "topic": topic,
                "description": description,
                "todos": todos,
            }
        )
        return "created"

    return StructuredTool.from_function(
        coroutine=_async_create_plan,
        name="create_plan",
        description="create plan",
    )


def _submit_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_async_submit_result,
        name="submit_result",
        description="submit",
    )


def _add_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_async_add_numbers,
        name="add_numbers",
        description="add",
    )


def _sync_add_tool() -> StructuredTool:
    return StructuredTool.from_function(
        _add_numbers,
        name="add_numbers",
        description="add",
    )


def test_react_state_is_valid_typed_dict():
    state: ReactState = {
        "messages": [],
        "iteration_count": 0,
        "is_done": False,
        "final_output": None,
    }
    assert state["iteration_count"] == 0


def test_create_react_agent_returns_compiled_graph(dummy_tool):
    config = ReactAgentConfig(
        name="test",
        tools=[dummy_tool],
        termination=TerminationCondition(mode="no_tool_call"),
    )
    graph = create_react_agent(config)
    assert graph is not None
    assert hasattr(graph, "ainvoke")


def test_create_react_agent_with_tool_success_termination(submit_tool):
    config = ReactAgentConfig(
        name="test",
        tools=[submit_tool],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
    )
    graph = create_react_agent(config)
    assert graph is not None


def test_react_agent_terminates_on_no_tool_call(dummy_tool):
    config = ReactAgentConfig(
        name="test",
        tools=[dummy_tool],
        termination=TerminationCondition(mode="no_tool_call"),
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(content="Done, no tools needed.")

    async def _run():
        with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
            result = await graph.ainvoke({
                "messages": [HumanMessage(content="Hello")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            })
            assert result["is_done"] is True

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_react_agent_terminates_on_tool_success():
    config = ReactAgentConfig(
        name="test",
        tools=[_submit_tool()],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "submit_result", "args": {"result": "analysis complete"}}],
        )

    with (
        patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke),
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=[HumanMessage(content="Use a tool")]),
        ),
    ):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Analyze this")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })
        assert result["is_done"] is True
        assert result["final_output"] == {"result": "analysis complete"}


@pytest.mark.asyncio
async def test_react_agent_emits_retry_event_for_retryable_llm_failure():
    config = ReactAgentConfig(
        name="writer",
        tools=[],
        termination=TerminationCondition(mode="no_tool_call"),
    )
    graph = create_react_agent(config)
    retry_events: list[dict] = []

    async def _retry_event_sink(payload: dict) -> None:
        retry_events.append(payload)

    responses = [
        Exception("temporary upstream failure"),
        AIMessage(content="final answer"),
    ]

    async def _mock_invoke(*args, **kwargs):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="Hello")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            },
            config={
                "configurable": {
                    "runtime_state": {"session_id": "sess_001"},
                    "retry_event_sink": _retry_event_sink,
                },
            },
        )

    assert result["is_done"] is True
    assert retry_events == [
        {
            "session_id": "sess_001",
            "node": "writer",
            "attempt": 2,
            "max_attempts": 5,
            "error_type": "Exception",
            "error_message": "temporary upstream failure",
        }
    ]


@pytest.mark.asyncio
async def test_react_agent_executes_termination_tool_on_final_iteration():
    config = ReactAgentConfig(
        name="test",
        tools=[_submit_tool()],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
        max_iterations=1,
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "submit_result", "args": {"result": "done"}}],
        )

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Analyze this")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })

    assert result["is_done"] is True
    assert result["iteration_count"] == 1
    assert result["final_output"] == {"result": "done"}


@pytest.mark.asyncio
async def test_react_agent_executes_tool_call_and_stops():
    config = ReactAgentConfig(
        name="test",
        tools=[_add_tool()],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=2,
    )
    graph = create_react_agent(config)

    call_count = 0

    async def mock_invoke_with_tools(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return AIMessage(
            content="",
            tool_calls=[{"id": f"call_{call_count}", "name": "add_numbers", "args": {"a": 1, "b": 2}}],
        )

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=mock_invoke_with_tools):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Keep calling tools")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })
        assert result["is_done"] is True
        assert result["iteration_count"] == 2


@pytest.mark.asyncio
async def test_react_agent_streams_tool_events_for_frontend():
    config = ReactAgentConfig(
        name="test",
        tools=[_submit_tool()],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "submit_result", "args": {"result": "done"}}],
        )

    tool_events = []
    with (
        patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke),
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=[HumanMessage(content="Use a tool")]),
        ),
    ):
        async for event in graph.astream_events(
            {
                "messages": [HumanMessage(content="Analyze this")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            },
            version="v2",
        ):
            if event["event"] in {"on_tool_start", "on_tool_end"}:
                tool_events.append(event)

    assert [event["event"] for event in tool_events] == ["on_tool_start", "on_tool_end"]
    assert [event["name"] for event in tool_events] == ["submit_result", "submit_result"]
    assert tool_events[0]["metadata"]["tool_call_id"] == "call_1"
    assert tool_events[1]["metadata"]["tool_call_id"] == "call_1"
    assert tool_events[0]["data"]["input"] == {"result": "done"}
    assert tool_events[1]["data"]["output"] == "submitted: done"


@pytest.mark.asyncio
async def test_react_agent_continues_after_auxiliary_tool_until_termination_tool():
    config = ReactAgentConfig(
        name="test",
        tools=[_add_tool(), _submit_tool()],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
        max_iterations=3,
    )
    graph = create_react_agent(config)

    responses = [
        AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "add_numbers", "args": {"a": 1, "b": 2}}],
        ),
        AIMessage(
            content="",
            tool_calls=[{"id": "call_2", "name": "submit_result", "args": {"result": "done"}}],
        ),
    ]

    async def _mock_invoke(*args, **kwargs):
        return responses.pop(0)

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Use a helper first")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })

    assert result["is_done"] is True
    assert result["iteration_count"] == 2
    assert result["final_output"] == {"result": "done"}


@pytest.mark.asyncio
async def test_react_agent_ignores_no_tool_response_until_termination_tool():
    config = ReactAgentConfig(
        name="test",
        tools=[_add_tool(), _submit_tool()],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
        max_iterations=4,
    )
    graph = create_react_agent(config)

    responses = [
        AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "add_numbers", "args": {"a": 1, "b": 2}}],
        ),
        AIMessage(content="I reviewed the intermediate result."),
        AIMessage(
            content="",
            tool_calls=[{"id": "call_2", "name": "submit_result", "args": {"result": "done"}}],
        ),
    ]

    async def _mock_invoke(*args, **kwargs):
        return responses.pop(0)

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Use a helper first")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })

    assert result["is_done"] is True
    assert result["iteration_count"] == 3
    assert result["final_output"] == {"result": "done"}


@pytest.mark.asyncio
async def test_react_agent_raises_when_tool_success_lacks_termination_tool():
    config = ReactAgentConfig(
        name="test",
        tools=[_add_tool(), _submit_tool()],
        termination=TerminationCondition(mode="tool_success", tool_name="submit_result"),
        max_iterations=2,
    )
    graph = create_react_agent(config)

    responses = [
        AIMessage(content="I reviewed it."),
        AIMessage(content="Still done in plain text."),
    ]

    async def _mock_invoke(*args, **kwargs):
        return responses.pop(0)

    with (
        patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke),
        pytest.raises(RuntimeError, match="submit_result"),
    ):
        await graph.ainvoke({
            "messages": [HumanMessage(content="Use the submit tool")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })


@pytest.mark.asyncio
async def test_react_agent_recovers_malformed_create_plan_todos_invalid_tool_call():
    executed_calls: list[dict[str, object]] = []
    config = ReactAgentConfig(
        name="composer",
        tools=[_create_plan_tool(executed_calls)],
        termination=TerminationCondition(mode="tool_success", tool_name="create_plan"),
        max_iterations=1,
    )
    graph = create_react_agent(config)
    malformed_args = (
        '{"topic":"Rewrite","description":"Make a plan","todos":'
        '[{"title":"Beat 1","content":"line1\nline2"},'
        '{"title":"Beat 2","content":"done"}]}'
    )

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            invalid_tool_calls=[
                invalid_tool_call(
                    id="call_1",
                    name="create_plan",
                    args=malformed_args,
                    error="invalid json in todos array",
                )
            ],
        )

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Create a plan")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })

    assert result["is_done"] is True
    assert result["final_output"] == {
        "topic": "Rewrite",
        "description": "Make a plan",
        "todos": [
            {"title": "Beat 1", "content": "line1\nline2"},
            {"title": "Beat 2", "content": "done"},
        ],
    }
    assert executed_calls == [result["final_output"]]


@pytest.mark.asyncio
async def test_react_agent_emits_tool_error_for_unrecoverable_invalid_tool_call_with_existing_id():
    executed_calls: list[dict[str, object]] = []
    config = ReactAgentConfig(
        name="composer",
        tools=[_create_plan_tool(executed_calls)],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=1,
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            invalid_tool_calls=[
                invalid_tool_call(
                    id="call_1",
                    name="create_plan",
                    args="<<<<",
                    error="invalid json",
                )
            ],
        )

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Create a plan")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })

    assert executed_calls == []
    assert isinstance(result["messages"][-1], ToolMessage)
    assert result["messages"][-1].tool_call_id == "call_1"
    assert '"reason": "malformed_tool_call"' in result["messages"][-1].content
    assert "create_plan" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_react_agent_synthesizes_tool_call_id_for_unrecoverable_invalid_tool_call():
    executed_calls: list[dict[str, object]] = []
    config = ReactAgentConfig(
        name="composer",
        tools=[_create_plan_tool(executed_calls)],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=1,
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            invalid_tool_calls=[
                {
                    "name": "create_plan",
                    "args": "<<<<",
                    "error": "invalid json",
                    "type": "invalid_tool_call",
                }
            ],
        )

    with patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke):
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Create a plan")],
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        })

    assistant_message = result["messages"][-2]
    tool_message = result["messages"][-1]
    assert executed_calls == []
    assert isinstance(assistant_message, AIMessage)
    assert isinstance(tool_message, ToolMessage)
    assert len(assistant_message.tool_calls) == 1
    synthesized_id = assistant_message.tool_calls[0]["id"]
    assert isinstance(synthesized_id, str) and synthesized_id
    assert tool_message.tool_call_id == synthesized_id


def test_invoke_tool_executes_sync_structured_tool_without_executor():
    async def _run():
        result = await _invoke_tool(_sync_add_tool(), {"a": 2, "b": 3})
        assert result == 5

    asyncio.run(_run())


class CaptureConfigInput(BaseModel):
    value: str


class CaptureConfigTool(AgentTool):
    name: str = "capture_config"
    description: str = "capture config"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = CaptureConfigInput

    async def _execute(self, value: str) -> str:
        return value


@pytest.mark.asyncio
async def test_react_agent_passes_runtime_config_and_tool_call_id_to_agent_tools():
    captured = []

    async def post_hook(ctx):
        captured.append(ctx)
        return HookResult()

    config = ReactAgentConfig(
        name="test",
        tools=[CaptureConfigTool(_post_hooks=[post_hook])],
        termination=TerminationCondition(mode="tool_success", tool_name="capture_config"),
    )
    graph = create_react_agent(config)

    async def _mock_invoke(*args, **kwargs):
        return AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "capture_config", "args": {"value": "done"}}],
        )

    with (
        patch("app.agent_runtime.graph.react_agent._invoke_model", side_effect=_mock_invoke),
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=[HumanMessage(content="Use a tool")]),
        ),
    ):
        await graph.ainvoke(
            {
                "messages": [HumanMessage(content="Use a tool")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            },
            config={
                "configurable": {
                    "db_session": "session",
                    "runtime_state": {"active_agent": "writer"},
                }
            },
        )

    assert captured[0].tool_call_id == "call_1"
    assert captured[0].config["configurable"]["db_session"] == "session"
