from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_runtime.agents.definitions import (
    DEFAULT_AGENT_DEFINITIONS,
    load_agent_definition,
    load_all_agent_definitions,
)
from app.agent_runtime.agents.tool_categories import get_tool_names_for_categories
from app.agent_runtime.graph.config import build_child_config, get_inject_queue
from app.agent_runtime.graph.node_events import with_node_events
from app.agent_runtime.graph.orchestrator.state import OrchestratorState
from app.agent_runtime.graph.react_agent import create_react_agent
from app.agent_runtime.model_config import to_client_model_config
from app.agent_runtime.tools import ToolRegistry
from app.agent_runtime.tools.impls.skill.skill import skill_tool_names_for_definition
from app.agent_runtime.tools.hooks.auth import auth_hook
from app.agent_runtime.tools.hooks.chapter_refresh import chapter_refresh_post_hook
from app.agent_runtime.tools.hooks.dispatch_description import (
    build_dispatch_subagent_description_hook,
)
from app.agent_runtime.tools.hooks.note_refresh import note_refresh_post_hook
from app.agent_runtime.tools.hooks.world_entry_refresh import world_entry_refresh_post_hook
from app.agent_runtime.types import ReactAgentConfig, TerminationCondition
from app.models.clients.model_factory import ModelConfig, create_chat_model

DEFAULT_PRIMARY_TOOL_CATEGORIES = (
    "orchestration",
    "interaction",
    "plan",
    "chapter_read",
    "summary_read",
    "world_read",
)


async def _primary_tool_names(config: RunnableConfig | None, agent_key: str = "primary") -> list[str]:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    db_session = configurable.get("db_session") if isinstance(configurable, dict) else None
    if db_session is None:
        return list(get_tool_names_for_categories(DEFAULT_PRIMARY_TOOL_CATEGORIES))
    definition = await load_agent_definition(db_session, agent_key)
    return list(get_tool_names_for_categories(definition.enabled_tool_categories)) + list(
        await skill_tool_names_for_definition(definition, db_session)
    )


async def _primary_build_hooks(
    config: RunnableConfig | None,
    agent_key: str = "primary",
):
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    db_session = configurable.get("db_session") if isinstance(configurable, dict) else None
    if db_session is None:
        definitions = dict(DEFAULT_AGENT_DEFINITIONS)
    else:
        definitions = await load_all_agent_definitions(db_session)
    return [
        build_dispatch_subagent_description_hook(
            agent_definitions=definitions,
            primary_agent_key=agent_key,
        )
    ]


def _primary_messages(state: OrchestratorState) -> list[BaseMessage]:
    messages = list(state.get("messages") or [])
    user_request = state.get("user_request") or ""
    if user_request:
        messages.append(HumanMessage(content=user_request))
    return messages


async def primary_node(
    state: OrchestratorState,
    config: RunnableConfig | None = None,
) -> dict:
    """Run the Primary Agent as the only parent graph node."""
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    runtime_model_config = (
        configurable.get("model_config") if isinstance(configurable, dict) else None
    )
    if not isinstance(runtime_model_config, dict):
        raise ValueError("Agent 运行时模型配置不可用")
    model_config = ModelConfig(**to_client_model_config(runtime_model_config))
    model = create_chat_model(model_config)
    agent_key = state.get("agent_key", "primary")
    tool_state = dict(state)
    tool_state["model_config"] = dict(runtime_model_config)
    tool_state["active_agent"] = agent_key

    agent_config = ReactAgentConfig(
        name=agent_key,
        tools=cast(
            list[BaseTool],
            ToolRegistry.get_tools(
                names=await _primary_tool_names(config, agent_key=agent_key),
                state=tool_state,
                build_hooks=await _primary_build_hooks(config, agent_key=agent_key),
                pre_hooks=[auth_hook],
                post_hooks=[chapter_refresh_post_hook, note_refresh_post_hook, world_entry_refresh_post_hook],
            ),
        ),
        termination=TerminationCondition(mode="no_tool_call"),
    )
    react_graph = create_react_agent(
        agent_config,
        model=model,
        inject_queue=get_inject_queue(config),
    )

    effective_state = dict(state)
    effective_state["model_config"] = dict(runtime_model_config)
    effective_state["active_agent"] = agent_key
    await react_graph.ainvoke(
        {
            "messages": _primary_messages(state),
            "iteration_count": 0,
            "is_done": False,
            "final_output": None,
        },
        config=build_child_config(config, effective_state),
    )

    return {"is_completed": True, "active_agent": agent_key}


def build_orchestrator_graph(checkpointer=None) -> CompiledStateGraph:
    builder = StateGraph(cast(Any, OrchestratorState))
    primary_action = cast(
        Callable[[dict[str, Any], RunnableConfig | None], Awaitable[dict[str, Any]]],
        primary_node,
    )
    primary_with_events = cast(
        Callable[[dict[str, Any], RunnableConfig | None], Awaitable[dict[str, Any]]],
        with_node_events("primary", primary_action),
    )
    builder.add_node("primary", cast(Any, primary_with_events))
    builder.add_edge(START, "primary")
    builder.add_edge("primary", END)
    return cast(CompiledStateGraph, builder.compile(checkpointer=checkpointer))
