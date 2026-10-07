import asyncio
import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool

from app.agent_runtime.graph.react_agent import create_react_agent
from app.agent_runtime.types import ReactAgentConfig, TerminationCondition


@pytest.mark.asyncio
@pytest.mark.parametrize("targets", [["a", "a", "a"], ["a", "b", "a"]])
async def test_notify_rejects_duplicate_targets_but_allows_later_batches(
    monkeypatch, targets
):
    started = set()
    expected_targets = set(targets)
    all_started = asyncio.Event()
    release = asyncio.Event()
    executed = []

    async def notify_subagent(dispatch_id: str, prompt: str) -> str:
        executed.append((dispatch_id, prompt))
        started.add(dispatch_id)
        if started == expected_targets:
            all_started.set()
        await release.wait()
        return json.dumps({"result": prompt})

    tool = StructuredTool.from_function(
        coroutine=notify_subagent, name="notify_subagent", description="notify"
    )
    responses = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": f"call-{index}",
                        "name": "notify_subagent",
                        "args": {"dispatch_id": target, "prompt": f"prompt-{index}"},
                    }
                    for index, target in enumerate(targets)
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "follow-up",
                        "name": "notify_subagent",
                        "args": {"dispatch_id": "a", "prompt": "next batch"},
                    }
                ],
            ),
            AIMessage(content="done"),
        ]
    )

    async def invoke_model(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr(
        "app.agent_runtime.graph.react_agent._invoke_model", invoke_model
    )
    model = Mock()
    model.bind_tools.return_value = model
    graph = create_react_agent(
        ReactAgentConfig(
            name="build",
            tools=[tool],
            termination=TerminationCondition(mode="no_tool_call"),
            max_iterations=3,
        ),
        model=model,
    )
    rejected_events = []

    async def sink(payload):
        rejected_events.append(payload)

    task = asyncio.create_task(
        graph.ainvoke(
            {"messages": [HumanMessage(content="go")], "iteration_count": 0},
            config={"configurable": {"tool_result_sink": sink}},
        )
    )
    try:
        # Distinct targets must start concurrently while the first is blocked.
        await asyncio.wait_for(all_started.wait(), timeout=2)
        assert set(executed) == {
            (target, f"prompt-{targets.index(target)}") for target in expected_targets
        }
        release.set()
        result = await asyncio.wait_for(task, timeout=2)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in messages] == [
        "call-0",
        "call-1",
        "call-2",
        "follow-up",
    ]
    seen = set()
    rejected = []
    for index, target in enumerate(targets):
        payload = json.loads(messages[index].content)
        if target in seen:
            assert payload["code"] == "conflict"
            assert payload["success"] is False
            rejected.append(f"call-{index}")
        else:
            assert payload == {"result": f"prompt-{index}"}
        seen.add(target)
    assert executed.count(("a", "next batch")) == 1
    assert json.loads(messages[-1].content) == {"result": "next batch"}
    assert [event["tool_call_id"] for event in rejected_events] == rejected
