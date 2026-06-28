from unittest.mock import Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphInterrupt
from pydantic import BaseModel

from app.agent_runtime.graph.react_agent import create_react_agent
from app.agent_runtime.tools.base import AgentTool, HookContext, HookResult
from app.agent_runtime.types import ReactAgentConfig, TerminationCondition


class _AuditProbe:
    def __init__(self) -> None:
        self.responses: list[dict] = []
        self.tools: list[dict] = []
        self.finished: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.finish(status="error" if exc else "success")
        return False

    def record_response(self, **kwargs):
        self.responses.append(kwargs)

    def record_tool_call(self, **kwargs):
        self.tools.append(kwargs)

    async def finish(self, status: str = "success"):
        self.finished.append(status)


def _submit_result(result: str) -> str:
    return "{\"ok\": true}"


async def _async_submit_result(result: str) -> str:
    return _submit_result(result)


def _submit_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_async_submit_result,
        name="submit_result",
        description="submit",
    )


class _InterruptInput(BaseModel):
    value: str


async def _blocking_approval_hook(ctx: HookContext) -> HookResult:
    return HookResult(
        proceed=False,
        interrupt_payload={
            "type": "tool_approval",
            "tool_name": ctx.tool_name,
            "args": ctx.args,
        },
    )


class _ApprovalInterruptTool(AgentTool):
    name: str = "create_plan"
    description: str = "interrupt before execution"
    access_level: str = "write"
    args_schema: type[BaseModel] = _InterruptInput

    async def _execute(self, value: str) -> str:
        return f"executed:{value}"


@pytest.mark.asyncio
async def test_react_agent_records_audit_for_model_and_tool_call() -> None:
    audit = _AuditProbe()
    collector = Mock()
    collector.llm_call.return_value = audit
    model = Mock()
    model.bind_tools.return_value = model
    response = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_1",
                "name": "submit_result",
                "args": {"result": "done"},
            }
        ],
        response_metadata={
            "usage": {
                "input_tokens": 12,
                "output_tokens": 4,
                "total_tokens": 16,
            }
        },
    )
    config = ReactAgentConfig(
        name="writer",
            tools=[_submit_tool()],
        termination=TerminationCondition(
            mode="tool_success",
            tool_name="submit_result",
        ),
        max_iterations=2,
    )
    graph = create_react_agent(config, model=model)

    async def _mock_invoke(*args, **kwargs):
        return response

    with patch(
        "app.agent_runtime.graph.react_agent._invoke_model",
        side_effect=_mock_invoke,
    ):
        await graph.ainvoke(
            {
                "messages": [HumanMessage(content="go")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            },
            config={
                "configurable": {
                    "audit_collector": collector,
                    "runtime_state": {
                        "model_config": {
                            "provider_type": "openai",
                            "model_id": "gpt-test",
                        }
                    },
                }
            },
        )

    collector.llm_call.assert_called_once()
    _, kwargs = collector.llm_call.call_args
    assert kwargs["agent_node"] == "writer"
    assert kwargs["model_id"] == "gpt-test"
    assert kwargs["model_provider"] == "openai"
    assert audit.responses[0]["usage"]["total_tokens"] == 16
    assert audit.tools[0]["tool_name"] == "submit_result"
    assert audit.tools[0]["tool_args"] == {"result": "done"}
    assert audit.tools[0]["success"] is True
    assert audit.finished == ["success"]


@pytest.mark.asyncio
async def test_react_agent_finishes_audit_when_tool_approval_interrupts() -> None:
    audit = _AuditProbe()
    collector = Mock()
    collector.llm_call.return_value = audit
    model = Mock()
    model.bind_tools.return_value = model
    response = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_1",
                "name": "create_plan",
                "args": {"value": "plan child beats"},
            }
        ],
    )
    tool = _ApprovalInterruptTool(
        _state={"session_id": "child-thread-1", "project_id": "project-1"},
        _pre_hooks=[_blocking_approval_hook],
    )
    config = ReactAgentConfig(
        name="composer",
        tools=[tool],
        termination=TerminationCondition(mode="no_tool_call"),
        max_iterations=2,
    )
    graph = create_react_agent(config, model=model)

    async def _mock_invoke(*args, **kwargs):
        return response

    with patch(
        "app.agent_runtime.graph.react_agent._invoke_model",
        side_effect=_mock_invoke,
    ), patch(
        "langgraph.types.interrupt",
        side_effect=GraphInterrupt(()),
    ):
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="go")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            },
            config={
                "configurable": {
                    "audit_collector": collector,
                    "runtime_state": {
                        "model_config": {
                            "provider_type": "openai",
                            "model_id": "gpt-test",
                        }
                    },
                }
            },
        )

    assert result["messages"][-1].tool_calls[0]["name"] == "create_plan"
    assert audit.responses[0]["tool_calls"][0]["name"] == "create_plan"
    assert audit.tools == []
    assert audit.finished == ["success"]
