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
                    else (
                        str(reply.content) + "\n[交接已因步骤上限或无效目标停止。]"
                        if target == END
                        else (state.get("final_output") or "")
                    ),
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


def ui_node(kind, children=None, **props):
    node = {"type": kind, "props": props, "children": children}
    if kind in {"Input", "TextArea"} and props.get("label"):
        return {
            "type": "Flex",
            "props": {"direction": "column", "gap": "2", "minWidth": "0"},
            "children": [
                {
                    "type": "Text",
                    "props": {"size": "2", "weight": "medium"},
                    "children": props["label"],
                },
                node,
            ],
        }
    return node


UI_CSS = """
:scope { --example-accent: var(--accent-9); }
.example-page { width: 100%; max-width: 1100px; margin: 0 auto; min-width: 0; }
.example-panel { padding: 20px; min-width: 0; }
.example-title { color: var(--accent-11); }
.example-actions { flex-wrap: wrap; }
.example-output { display: block; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 24rem; overflow: auto; }
.example-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.example-metric strong { display: block; font-size: 26px; margin-top: 8px; }
.example-table { overflow-x: auto; }
.example-conflict { border: 1px solid var(--orange-7); padding: 12px; border-radius: 8px; }
.example-compact { padding: 8px; }
@media (max-width: 640px) {
  .example-panel { padding: 12px; }
  .example-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .example-actions > button { flex: 1 1 auto; }
}
"""


def ui_button(title, action, **props):
    return ui_node("Button", title, onPress=action, **props)


def ui_row(*children):
    return ui_node(
        "Flex", list(children), gap="3", align="center", className="example-actions"
    )


def ui_panel(*children):
    return ui_node(
        "Card",
        ui_node("Flex", list(children), direction="column", gap="4"),
        className="example-panel",
    )


def ui_status(state):
    return ui_node(
        "Text",
        state.get("status", ""),
        id="status",
        role="status",
        size="2",
        color="gray",
    )


def ui_document(*children, compact=False):
    return {
        "css": UI_CSS,
        "tree": ui_node(
            "Flex",
            list(children),
            direction="column",
            gap="4",
            **{
                "className": "example-page" + (" example-compact" if compact else ""),
            },
        ),
    }


async def ui_state(ctx, params, global_default=False):
    context = params.get("context", {})
    key = (
        "ui:"
        + params.get("viewId", "main")
        + ":"
        + str(context.get("projectId") or "global")
    )
    state = await ctx.storage.get(key, {})
    if "project" not in state:
        projects = await ctx.data.list_projects()
        state["project"] = context.get("projectId") or (
            "" if global_default or not projects else projects[0]["id"]
        )
    return key, state


async def ui_render(ctx, params):
    _, state = await ui_state(ctx, params)
    result = await last(ctx, {})
    trace = [
        ui_node(
            "Text", f"{item['round']}. {item['from']} → {item['to']}：{item['reason']}"
        )
        for item in (result or {}).get("handoffs", [])
    ]
    return ui_document(
        ui_node("Heading", "Handoff 写作工作流", className="example-title"),
        ui_node(
            "Text",
            "规划 Agent → 写作 Agent → 审稿 Agent。模型通过 handoff 工具交接控制权；审稿可将反馈交回写作。",
            color="gray",
            size="2",
        ),
        ui_panel(
            ui_node(
                "Grid",
                [
                    ui_node(
                        "ProjectSelector",
                        label="选择项目",
                        value=state["project"],
                        onChange="project",
                    ),
                    ui_node(
                        "ModelSelector",
                        label="调用模型",
                        value=state.get("model", ""),
                        onChange="model",
                        editable=False,
                    ),
                ],
                columns={"initial": "1", "sm": "2"},
                gap="4",
            ),
            ui_node(
                "TextArea",
                label="写作任务",
                value=state.get(
                    "prompt", "写一段旅人在山谷遇见旧友的故事，保持人物动机一致。"
                ),
                onChange="prompt",
                rows=4,
                resize="vertical",
            ),
            ui_row(
                ui_button("运行工作流", "run", disabled=not state.get("model")),
                ui_button("演示交接（不调用模型）", "demo", variant="soft"),
            ),
            ui_status(state),
        ),
        ui_panel(
            ui_node("Heading", "项目默认工作流", size="3"),
            ui_node(
                "Text",
                "只影响选中项目之后发起的 Agent 回合，可随时恢复内置工作流。",
                size="2",
            ),
            ui_row(
                ui_button(
                    "为此项目启用 Handoff", "select", disabled=not state["project"]
                ),
                ui_button(
                    "恢复内置工作流",
                    "reset",
                    variant="soft",
                    disabled=not state["project"],
                ),
            ),
        ),
        ui_panel(
            ui_node("Heading", "交接记录", size="3"),
            ui_node(
                "Flex",
                trace or [ui_node("Text", "运行后在这里显示交接记录。", color="gray")],
                direction="column",
                gap="2",
                id="trace",
            ),
            ui_node("Heading", "最终输出", size="3"),
            ui_node(
                "Code",
                (result or {}).get("text", "尚未运行工作流。"),
                id="output",
                className="example-output",
            ),
            ui_row(
                ui_button(
                    "保存为项目笔记",
                    "save",
                    variant="soft",
                    disabled=not result or not state["project"],
                ),
                ui_button("导出结果", "download", variant="soft", disabled=not result),
            ),
        ),
    )


async def ui_action(ctx, params):
    import json

    key, state = await ui_state(ctx, params)
    action = params["id"]
    if action in {"project", "model", "prompt"}:
        state[action] = params["value"]
    elif action in {"run", "demo"}:
        await run(
            ctx,
            {
                "projectId": state["project"],
                "modelId": state.get("model"),
                "prompt": state.get(
                    "prompt", "写一段旅人在山谷遇见旧友的故事，保持人物动机一致。"
                ),
                "demo": action == "demo",
            },
        )
        state["status"] = (
            "演示完成（没有调用模型）" if action == "demo" else "工作流完成"
        )
    elif action in {"select", "reset"}:
        await ctx.call(
            "workflow.select",
            {
                "projectId": state["project"],
                "provider": "handoff" if action == "select" else None,
            },
        )
        state["status"] = (
            "已为此项目启用 Handoff 工作流"
            if action == "select"
            else "已恢复内置工作流"
        )
    elif action in {"save", "download"}:
        result = await last(ctx, {})
        if not result or not result.get("text"):
            raise ValueError("请先运行工作流")
        if action == "download":
            return {
                "effects": [
                    {
                        "method": "ui.download",
                        "params": {
                            "name": "handoff-result.json",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                            "mime": "application/json",
                        },
                    }
                ]
            }
        if result.get("projectId") != state["project"]:
            raise ValueError("请先为当前项目运行工作流，避免将其他项目的结果写入此项目")
        await ctx.notes.create(
            {"title": "Handoff 写作结果", "content": result["text"]}, state["project"]
        )
        state["status"] = "已保存为项目笔记"
    else:
        raise ValueError("Unknown UI action")
    await ctx.storage.set(key, state)


def register(host):
    host.register_command("ui.render", ui_render)
    host.register_command("ui.action", ui_action)
    host.register_graph("handoff", handoff_graph)
    host.register_command("workflow.run", run)
    host.register_command("workflow.last", last)
