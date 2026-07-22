import json
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from app.agent_runtime.runner.session_runner import SessionRunner
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.tools.base import AgentTool, HookResult
from app.agent_runtime.tools.registry import ToolRegistry


def _edge_source(edge):
    return edge[0] if isinstance(edge, tuple) else edge.source


def _edge_target(edge):
    return edge[1] if isinstance(edge, tuple) else edge.target


def test_build_orchestrator_graph_has_only_primary_runtime_node():
    from app.agent_runtime.graph.orchestrator.graph import build_orchestrator_graph

    graph = build_orchestrator_graph()

    assert graph is not None
    assert hasattr(graph, "ainvoke")

    graph_data = graph.get_graph()
    node_names = set(graph_data.nodes.keys())
    assert "primary" in node_names
    assert not {"explore", "composer", "auditor", "writer", "actor", "reviewer"} & node_names

    start_edges = [edge for edge in graph_data.edges if _edge_source(edge) == "__start__"]
    end_edges = [edge for edge in graph_data.edges if _edge_target(edge) == "__end__"]
    assert any(_edge_target(edge) == "primary" for edge in start_edges)
    assert any(_edge_source(edge) == "primary" for edge in end_edges)


def test_session_runner_constructor_no_longer_accepts_mode():
    with pytest.raises(TypeError):
        SessionRunner(
            session_id="session-1",
            task_id="task-1",
            mode="agent",
            model_config={"max_context_tokens": 8000},
            project_id="project-1",
        )


def test_session_runner_uses_session_id_as_parent_thread_id():
    runner = SessionRunner(
        session_id="session-parent",
        task_id="task-1",
        model_config={"max_context_tokens": 8000},
        project_id="project-1",
    )

    config = runner._build_runtime_config(
        runtime_session=object(),
        runtime_context={},
        audit_context=object(),
    )

    assert config["configurable"]["thread_id"] == "session-parent"
    assert not hasattr(runner, "mode")


class _ApprovalToolInput(BaseModel):
    value: str


async def _interrupt_for_approval(context) -> HookResult:
    return HookResult(
        proceed=False,
        interrupt_payload={
            "type": "tool_approval",
            "tool_name": context.tool_name,
            "args": context.args,
        },
    )


class _OrchestratorApprovalTool(AgentTool):
    name: str = "orchestrator_approval_tool"
    description: str = "requires approval"
    access_level: str = "write"
    args_schema: type[BaseModel] = _ApprovalToolInput

    async def _execute(self, value: str) -> str:
        return json.dumps({"success": True, "value": value})


_ORCHESTRATOR_APPROVAL_TOOL_NAME = "orchestrator_approval_tool"


@pytest.mark.asyncio
async def test_orchestrator_resumes_all_parallel_tool_approvals_once() -> None:
    from app.agent_runtime.graph.orchestrator.graph import build_orchestrator_graph

    registered_tools = dict(ToolRegistry._tools)
    ToolRegistry._tools[_ORCHESTRATOR_APPROVAL_TOOL_NAME] = _OrchestratorApprovalTool
    graph = build_orchestrator_graph(checkpointer=InMemorySaver())
    executed_values: list[str] = []
    original_execute = _OrchestratorApprovalTool._execute

    async def execute(self, value: str) -> str:
        executed_values.append(value)
        return await original_execute(self, value)

    response = AIMessage(
        content="",
        tool_calls=[
            {
                "id": f"call_{index}",
                "name": _ORCHESTRATOR_APPROVAL_TOOL_NAME,
                "args": {"value": str(index)},
            }
            for index in range(1, 6)
        ],
    )
    runtime_config = {
        "configurable": {
            "thread_id": "orchestrator-parallel-approval",
            "db_session": object(),
            "model_config": {
                "provider_type": "openai",
                "model_id": "gpt-test",
                "api_key": "key",
                "base_url": "",
                "max_context_tokens": 8000,
            },
        }
    }
    initial_state = {
        "session_id": "orchestrator-parallel-approval",
        "task_id": "task-1",
        "project_id": "project-1",
        "model_config": runtime_config["configurable"]["model_config"],
        "agent_key": "build",
        "messages": [],
        "user_request": "run both",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "current_revision_id": "rev-1",
    }

    responses = [response, AIMessage(content="done")]

    async def invoke_model(*args, **kwargs):
        return responses.pop(0)

    class _Model:
        def bind_tools(self, _tools):
            return self

    try:
        with (
            patch(
                "app.agent_runtime.graph.orchestrator.graph.create_chat_model",
                return_value=_Model(),
            ),
            patch(
                "app.agent_runtime.graph.orchestrator.graph._primary_tool_names",
                AsyncMock(return_value=[_ORCHESTRATOR_APPROVAL_TOOL_NAME]),
            ),
            patch(
                "app.agent_runtime.graph.orchestrator.graph._primary_build_hooks",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.agent_runtime.graph.orchestrator.graph.auth_hook",
                _interrupt_for_approval,
            ),
            patch(
                "app.agent_runtime.graph.react_agent._invoke_model",
                side_effect=invoke_model,
            ),
            patch(
                "app.agent_runtime.graph.react_agent.build_context_parts",
                AsyncMock(return_value=[ContextMessage(role="user", content="run both")]),
            ),
            patch.object(_OrchestratorApprovalTool, "_execute", execute),
        ):
            await graph.ainvoke(initial_state, config=runtime_config)
            state = await graph.aget_state(runtime_config)
            interrupts = [
                interrupt
                for task in state.tasks
                for interrupt in getattr(task, "interrupts", ())
            ]
            assert [interrupt.value["tool_call_id"] for interrupt in interrupts] == ["call_1"]
            for index in range(1, 6):
                async for _event in graph.astream_events(
                    Command(
                        resume={
                            interrupts[0].id: {
                                "action_type": "tool_approval",
                                "approval_id": interrupts[0].id,
                                "approved": True,
                            }
                        }
                    ),
                    config=runtime_config,
                    version="v2",
                ):
                    pass
                resumed_state = await graph.aget_state(runtime_config)
                interrupts = [
                    interrupt
                    for task in resumed_state.tasks
                    for interrupt in getattr(task, "interrupts", ())
                ]
                if index < 5:
                    assert [interrupt.value["tool_call_id"] for interrupt in interrupts] == [
                        f"call_{index + 1}"
                    ]
                else:
                    assert resumed_state.next == ()
    finally:
        ToolRegistry._tools = registered_tools

    assert executed_values == [str(index) for index in range(1, 6)]
