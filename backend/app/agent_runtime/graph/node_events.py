from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig

from app.agent_runtime.runner.event_scope import SUBAGENT_CHILD_EVENT_TAG
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.socket import emit
from app.socket.handlers import agent_session_room, agent_subagent_session_room


NodePhase = Literal["start", "end"]
NodeStatus = Literal["running", "completed", "error"]
NodeFunc = Callable[[dict[str, Any], RunnableConfig | None], Awaitable[dict]]
NodeEventSink = Callable[[dict[str, Any]], Awaitable[None]]

CURRENT_NODE_KEY = "current_node"
LAST_NODE_KEY = "last_node"
PREVIOUS_NODE_KEY = "previous_node"


def with_node_events(node_name: str, node_func: NodeFunc) -> NodeFunc:
    async def wrapped(state: dict[str, Any], config: RunnableConfig | None = None) -> dict:
        session_id = str(state.get("session_id") or "")
        await emit_node_event(
            config,
            session_id=session_id,
            node=node_name,
            phase="start",
            status="running",
        )
        try:
            result = await node_func(state, config)
        except Exception:
            await emit_node_event(
                config,
                session_id=session_id,
                node=node_name,
                phase="end",
                status="error",
            )
            raise
        await emit_node_event(
            config,
            session_id=session_id,
            node=node_name,
            phase="end",
            status="completed",
        )
        return result

    wrapped.__name__ = getattr(node_func, "__name__", f"{node_name}_node")
    return wrapped


async def emit_node_event(
    config: RunnableConfig | None,
    *,
    session_id: str,
    node: str,
    phase: NodePhase,
    status: NodeStatus,
) -> None:
    if not session_id:
        return

    runtime_context = _get_runtime_context(config)
    previous_node = _previous_node(runtime_context)
    current_node: str | None = node
    if runtime_context is not None:
        if phase == "start":
            runtime_context[PREVIOUS_NODE_KEY] = previous_node
            runtime_context[CURRENT_NODE_KEY] = node
        else:
            previous_node = _string_or_none(runtime_context.get(PREVIOUS_NODE_KEY))
            if runtime_context.get(CURRENT_NODE_KEY) == node:
                runtime_context[CURRENT_NODE_KEY] = None
            runtime_context[LAST_NODE_KEY] = node
            current_node = _string_or_none(runtime_context.get(CURRENT_NODE_KEY))
    elif phase == "end":
        current_node = None

    payload = {
        "session_id": session_id,
        "node": node,
        "phase": phase,
        "status": status,
        "current_node": current_node,
        "previous_node": previous_node,
    }
    node_event_sink = _get_node_event_sink(config)
    if node_event_sink is not None:
        await node_event_sink(payload)

    try:
        buffer = get_agent_event_replay_buffer()
        room = (
            agent_subagent_session_room(session_id)
            if _is_subagent_child_config(config)
            else agent_session_room(session_id)
        )
        async with buffer.session_lock(session_id):
            if phase == "end":
                buffer.clear_event_unlocked(session_id, "agent:retry")
            buffer.record_unlocked("agent:node", payload)
            await emit("agent:node", payload, room=room)
    except Exception:
        pass


def _get_runtime_context(config: RunnableConfig | None) -> MutableMapping[str, Any] | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    runtime_context = configurable.get("runtime_context")
    if isinstance(runtime_context, MutableMapping):
        return runtime_context
    return None


def _get_node_event_sink(config: RunnableConfig | None) -> NodeEventSink | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    value = configurable.get("node_event_sink")
    return value if callable(value) else None


def _is_subagent_child_config(config: RunnableConfig | None) -> bool:
    if not isinstance(config, dict):
        return False
    tags = config.get("tags")
    if not isinstance(tags, (list, tuple, set)):
        return False
    return SUBAGENT_CHILD_EVENT_TAG in tags


def _previous_node(runtime_context: MutableMapping[str, Any] | None) -> str | None:
    if runtime_context is None:
        return None
    return _string_or_none(runtime_context.get(CURRENT_NODE_KEY)) or _string_or_none(
        runtime_context.get(LAST_NODE_KEY)
    )


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
