"""Three-agent handoff graph. LangGraph Command changes the active node."""

import operator
import time
import uuid
from dataclasses import replace
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langchain_core.tools import StructuredTool
from pydantic import BaseModel


class HandoffInput(BaseModel):
    reason: str


class HandoffState(TypedDict):
    messages: Annotated[list, add_messages]
    handoffs: Annotated[list, operator.add]
    rounds: int
    final_output: str


INSTRUCTIONS = {
    "planner": "You are the planner in a handoff writing team. Clarify the story plan, then call handoff_to_writer to transfer control. Do not write the final chapter yourself.",
    "writer": "You are the writer in a handoff writing team. Draft or revise the story using the full conversation and feedback. Call handoff_to_reviewer when ready.",
    "reviewer": "You are the reviewer in a handoff writing team. Check consistency and the requested constraints. If changes are needed, call handoff_to_writer with feedback. Otherwise return the final accepted draft and finish.",
}
TARGETS = {
    "planner": ["writer"],
    "writer": ["reviewer", "planner"],
    "reviewer": ["writer"],
}


def handoff_graph(ctx, model):
    builder = StateGraph(HandoffState)
    for role in INSTRUCTIONS:

        async def node(state, config, role=role):
            tools = []
            for destination in TARGETS[role]:

                async def acknowledge(reason: str, destination=destination):
                    return "Handoff requested to " + destination + ": " + reason

                tools.append(
                    StructuredTool.from_function(
                        coroutine=acknowledge,
                        name="handoff_to_" + destination,
                        description="Transfer control and context to the "
                        + destination,
                        args_schema=HandoffInput,
                    )
                )
            tool_map = {tool.name: tool for tool in tools}
            if ctx.runtime.get("demo"):
                target = {"planner": "writer", "writer": "reviewer"}.get(role)
                reply = AIMessage(
                    content={
                        "planner": "规划完成",
                        "writer": "章节草稿：风穿过山谷，旅人终于抵达。",
                        "reviewer": "审核通过：风穿过山谷，旅人终于抵达。",
                    }[role],
                    tool_calls=[
                        {
                            "id": uuid.uuid4().hex,
                            "name": "handoff_to_" + target,
                            "args": {"reason": "交接下一位专家"},
                        }
                    ]
                    if target
                    else [],
                )
            else:
                conversation = await ctx.agent.context_messages(state["messages"])
                reply = await ctx.models.invoke(
                    model.bind_tools(tools),
                    [SystemMessage(INSTRUCTIONS[role]), *conversation],
                )
            updates = [reply]
            trace = []
            rounds = state.get("rounds", 0) + 1
            target = END
            for call in reply.tool_calls:
                candidate = call["name"].removeprefix("handoff_to_")
                valid = (
                    candidate in TARGETS[role] and rounds < ctx.settings["maxHandoffs"]
                )
                target = candidate if valid else END
                reason = call.get("args", {}).get("reason", "")
                if call["name"] in tool_map:
                    tool_config = {
                        **config,
                        "metadata": {
                            **config.get("metadata", {}),
                            "tool_call_id": call["id"],
                            "tool_call": call,
                        },
                    }
                    result = await tool_map[call["name"]].ainvoke(
                        {**call, "type": "tool_call"}, config=tool_config
                    )
                    updates.append(
                        result
                        if isinstance(result, ToolMessage)
                        else ToolMessage(
                            content=str(result),
                            tool_call_id=call["id"],
                            name=call["name"],
                        )
                    )
                else:
                    updates.append(
                        ToolMessage(
                            content="Unknown handoff target",
                            tool_call_id=call["id"],
                            name=call["name"],
                        )
                    )
                trace.append(
                    {
                        "from": role,
                        "to": candidate if valid else "end",
                        "reason": reason,
                        "round": rounds,
                    }
                )
            ctx.emit("handoff.step", {"agent": role, "next": target, "round": rounds})
            return Command(
                goto=target,
                update={
                    "messages": updates,
                    "handoffs": trace,
                    "rounds": rounds,
                    "final_output": str(reply.content)
                    if not reply.tool_calls
                    else (str(reply.content) + "\n[交接已因步骤上限或无效目标停止。]" if target == END else (state.get("final_output") or "")),
                },
            )

        builder.add_node(role, node)
    builder.add_edge(START, "planner")
    return builder.compile()


async def run(ctx, params):
    project_id = params.get("projectId")
    if project_id:
        await ctx.projects.get(project_id)
    demo = params.get("demo", False)
    if not params.get("prompt"):
        raise ValueError("请输入写作任务")
    model = None if demo else await ctx.models.create(params.get("modelId"))
    runtime = replace(
        ctx, runtime={**ctx.runtime, "project_id": project_id, "demo": demo}
    )
    graph = handoff_graph(runtime, model)
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(params["prompt"])],
            "handoffs": [],
            "rounds": 0,
            "final_output": "",
        },
        config={"recursion_limit": ctx.settings["maxHandoffs"] + 5},
    )
    output = {
        "handoffs": result["handoffs"],
        "rounds": result["rounds"],
        "text": result["final_output"],
        "demo": demo,
        "time": time.time(),
        "projectId": project_id,
    }
    await ctx.storage.set("lastRun", output)
    return output


async def last(ctx, params):
    return await ctx.storage.get("lastRun")


def register(host):
    host.register_graph("handoff", handoff_graph)
    host.register_command("workflow.run", run)
    host.register_command("workflow.last", last)
