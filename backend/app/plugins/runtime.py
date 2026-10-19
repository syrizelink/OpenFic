"""Shared SDK dispatch and Agent middleware/graph/tool adaptation."""

import asyncio
import copy
from contextvars import ContextVar

from app.plugins.services import bounded_json

EVENTS = frozenset(
    {
        "session.start",
        "session.end",
        "turn.start",
        "turn.step",
        "turn.complete",
        "prompt.submit",
        "prompt.compose",
        "prompt.section",
        "prompt.context",
        "tool.call",
        "tool.result",
        "tool.describe",
        "agent.spawn",
        "context.build",
        "editor.change",
        "data.changed",
        "ui.render",
        "ui.press",
        "ui.input",
        "ui.select",
    }
)
_executing_plugins: ContextVar[tuple[tuple[str, object], ...]] = ContextVar(
    "plugin_hook_stack", default=()
)


async def sdk_call(context, method: str, params: dict):
    if method == "api.request":
        return await context.api.request(**params)
    if method == "catalogue":
        from app.plugins.declarative import CATALOGUE
        from app.plugins.gateway import BusinessAPI
        from app.plugins.manifest import CAPABILITIES, UI_SLOTS, SDK_VERSION

        return {
            "version": SDK_VERSION,
            "capabilities": sorted(CAPABILITIES),
            "slots": UI_SLOTS,
            "events": sorted(EVENTS),
            "ui": CATALOGUE,
            **BusinessAPI.catalogue(),
        }
    if method == "data.projects":
        return await context.data.list_projects()
    if method == "data.entities":
        return await context.data.project_entities(params["projectId"])
    namespace, _, action = method.partition(".")
    if namespace in {"storage", "secrets", "files"} and action in {
        "get",
        "set",
        "delete",
        "keys",
        "read",
        "write",
        "list",
    }:
        # Secrets are write/delete/status only from frontend. Python plugins can read.
        if namespace == "secrets" and action == "get":
            raise PermissionError("Secrets cannot be read through the frontend bridge")
        service = getattr(context, namespace)
        return await getattr(service, action)(**params)
    if method == "http.request":
        return await context.http.request(**params)
    if method == "oauth.start":
        return await context.oauth.start(**params)
    if method == "models.complete":
        return await context.models.complete(**params)
    if method == "agent.tools":
        return context.agent.tools()
    if method in {"agent.start", "agent.send", "agent.cancel"}:
        return await getattr(context.agent, method.split(".")[1])(**params)
    if method == "events.emit":
        return context.emit(params["event"], params.get("data", {}))
    if method == "events.poll":
        context.require("events")
        return context.host.events(params.get("after", 0))
    if method == "hooks.preview":
        context.require("agent.hooks")
        if params["event"] not in EVENTS:
            raise ValueError("Unknown event")
        return await dispatch(
            params["event"],
            params.get("data", {}),
            context.data._session,
            host=context.host,
            runtime=context.runtime,
        )
    if method == "workflow.select":
        context.require("agent.graph")
        provider = params.get("provider")
        plugin = context.plugin
        if provider and provider not in plugin.registration.graphs:
            raise ValueError("Unknown graph provider")
        project_id = params["projectId"]
        await context.api.request("GET", f"/projects/{project_id}")
        import json

        path = context.host.root / ".workflows.json"
        selected = json.loads(path.read_text()) if path.exists() else {}
        if provider:
            selected[project_id] = f"{context.plugin_id}/{provider}"
        else:
            selected.pop(project_id, None)
        context.host._write_json(path, selected)
        return {"provider": f"{context.plugin_id}/{provider}" if provider else None}
    if method == "workflow.providers":
        context.require("agent.graph")
        return [
            {"id": f"{p.manifest.id}/{name}", "plugin": p.manifest.name}
            for p in context.host.plugins.values()
            if p.registration
            for name in p.registration.graphs
        ]
    if method == "log":
        context.log(params["message"], params.get("level", "info"))
        return None
    raise ValueError(f"Unsupported SDK method: {method}")


async def dispatch(
    event: str, payload: dict, session=None, *, host=None, runtime=None, terminal=None
):
    dispatch_identity = object()
    from app.plugins.host import active_host

    host = host or active_host()
    handlers = []
    if host:
        for plugin in list(host.plugins.values()):
            if not plugin.enabled or plugin.registration is None:
                continue
            for priority, handler in plugin.registration.hooks.get(event, []):
                handlers.append((priority, plugin.manifest.id, handler))
    handlers.sort(key=lambda item: (item[0], item[1]))

    async def step(index, data):
        if index == len(handlers):
            return await terminal(data) if terminal else data
        _, plugin_id, handler = handlers[index]
        if any(
            owner == plugin_id and identity is not dispatch_identity
            for owner, identity in _executing_plugins.get()
        ):
            return await step(index + 1, data)
        context = host.context(plugin_id, session, runtime)
        called = False
        next_result = None

        async def next_handler(value=None):
            nonlocal called, next_result
            if called:
                raise ValueError("Middleware next() may only be called once")
            called = True
            changed_data = data if value is None else value
            if event == "editor.change" and changed_data.get("content") != data.get(
                "content"
            ):
                context.require("editor.write")
            result = await step(index + 1, changed_data)
            next_result = copy.deepcopy(result)
            return result

        token = _executing_plugins.set(
            (*_executing_plugins.get(), (plugin_id, dispatch_identity))
        )
        try:
            async with asyncio.timeout(30):
                result = await handler(context, copy.deepcopy(data), next_handler)
            baseline = next_result if called else data
            if (
                event == "editor.change"
                and isinstance(result, dict)
                and result.get("content") != (baseline or {}).get("content")
            ):
                context.require("editor.write")
            return result
        except Exception as error:
            host._log(plugin_id, "hook", f"{event}: {error}", "error")
            raise
        finally:
            _executing_plugins.reset(token)

    return await step(0, payload)


async def model_messages(messages, session=None, *, runtime=None, host=None):
    """Runs on the final prompt, including transient and injected user messages."""
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
        convert_to_messages,
    )
    from app.plugins.host import active_host

    current = host or active_host()
    if current is None or not any(
        p.registration and p.registration.hooks for p in current.plugins.values()
    ):
        return messages

    data = [
        {
            "role": {
                "human": "user",
                "ai": "assistant",
                "AIMessageChunk": "assistant",
                "HumanMessageChunk": "user",
                "SystemMessageChunk": "system",
                "ToolMessageChunk": "tool",
            }.get(m.type, m.type),
            "content": m.content,
            "metadata": dict(m.response_metadata.get("openfic_context", {})),
            "additional_kwargs": dict(m.additional_kwargs),
            "response_metadata": dict(m.response_metadata),
            **({"name": m.name} if m.name else {}),
            **({"id": m.id} if m.id else {}),
            **({"tool_call_id": m.tool_call_id} if hasattr(m, "tool_call_id") else {}),
            **({"tool_calls": m.tool_calls} if getattr(m, "tool_calls", None) else {}),
            **(
                {
                    key: getattr(m, key)
                    for key in ("artifact", "status", "invalid_tool_calls")
                    if hasattr(m, key)
                }
            ),
            **(
                {"usage_metadata": m.usage_metadata}
                if getattr(m, "usage_metadata", None)
                else {}
            ),
        }
        for m in messages
    ]
    base = {
        "messages": data,
        "projectId": (runtime or {}).get("project_id"),
        "sessionId": (runtime or {}).get("session_id"),
        "agent": (runtime or {}).get("active_agent"),
    }
    base = await dispatch("context.build", base, session, host=host, runtime=runtime)
    sections = [
        {
            "id": f"{(m.get('metadata') or {}).get('part', 'system')}-{i}",
            "text": m["content"],
            "scope": "system",
        }
        for i, m in enumerate(base["messages"])
        if m["role"] == "system"
    ]
    section_sources = {
        section["id"]: message
        for section, message in zip(
            sections, (m for m in base["messages"] if m["role"] == "system")
        )
    }
    composed = await dispatch(
        "prompt.compose",
        {**base, "sections": sections},
        session,
        host=host,
        runtime=runtime,
    )
    sections = []
    for section in composed.get("sections", []):
        result = await dispatch(
            "prompt.section",
            {**base, "name": section["id"], "text": section["text"]},
            session,
            host=host,
            runtime=runtime,
        )
        sections.append(
            {
                **section_sources.get(section["id"], {"role": "system"}),
                "content": result.get("text"),
            }
        )
    final = []
    pending_sections = list(sections)
    system_indexes = [
        i for i, m in enumerate(base["messages"]) if m["role"] == "system"
    ]
    for index, message in enumerate(base["messages"]):
        if message["role"] == "system":
            if pending_sections:
                final.append(pending_sections.pop(0))
            if index == system_indexes[-1]:
                final.extend(pending_sections)
                pending_sections.clear()
        else:
            final.append(message)
    if pending_sections:
        final = [*pending_sections, *final]
    result = await dispatch(
        "prompt.context",
        {**base, "messages": final, "blocks": []},
        session,
        host=host,
        runtime=runtime,
    )
    final = result.get("messages", final)
    final.extend(
        {"role": "system", "content": b if isinstance(b, str) else b.get("text", "")}
        for b in result.get("blocks", [])
    )
    final = [message for message in final if message.get("content") is not None]
    bounded_json(final, 8 * 1024 * 1024)
    constructors = {
        "user": HumanMessage,
        "assistant": AIMessage,
        "system": SystemMessage,
        "tool": ToolMessage,
    }
    restored = []
    for message in final:
        fields = {k: v for k, v in message.items() if k not in {"metadata", "role"}}
        constructor = constructors.get(message["role"])
        restored.append(
            constructor(**fields)
            if constructor
            else convert_to_messages([{**fields, "role": message["role"]}])[0]
        )
    return restored


def plugin_tools(state: dict, names=None):
    from app.plugins.host import active_host
    from app.plugins.agent_tool import PluginAgentTool

    host = active_host()
    if host is None:
        return []
    return [
        PluginAgentTool(
            name=f"plugin_{plugin.manifest.id.replace('-', '_')}_{name}",
            description=spec["description"],
            args_schema=spec["schema"],
            access_level=spec["access_level"],
            _state=state,
            plugin_id=plugin.manifest.id,
            command_name=name,
            host=host,
        )
        for plugin in host.plugins.values()
        if plugin.enabled and plugin.registration
        for name, spec in plugin.registration.tools.items()
        if names is None
        or f"plugin_{plugin.manifest.id.replace('-', '_')}_{name}" in names
    ]


def plugin_tool_names_for_agent(agent_key: str, metadata=None) -> list[str]:
    """Build opts into extensions; other agents retain their original tool scope.

    Agent metadata may explicitly select plugin_tools (a list of full tool names).
    An empty list disables plugin tools, including for Build.
    """
    selection = (metadata or {}).get("plugin_tools")
    available = plugin_tools({})
    if selection is None:
        return [tool.name for tool in available] if agent_key == "build" else []
    if not isinstance(selection, (list, tuple)):
        return []
    return [tool.name for tool in available if tool.name in selection]


async def selected_graph(state, config, model):
    from app.plugins.host import active_host

    host = active_host()
    if host is None:
        return None
    import json

    path = host.root / ".workflows.json"
    selection = (json.loads(path.read_text()) if path.exists() else {}).get(
        state.get("project_id")
    )
    for plugin in host.plugins.values():
        if not plugin.registration or not plugin.registration.graphs:
            continue
        provider = (
            selection.removeprefix(plugin.manifest.id + "/")
            if selection and selection.startswith(plugin.manifest.id + "/")
            else None
        )
        if provider:
            session = (config or {}).get("configurable", {}).get("db_session")
            context = host.context(plugin.manifest.id, session, state)
            factory = plugin.registration.graphs.get(provider)
            if factory:
                graph = factory(context, model)
                if hasattr(graph, "__await__"):
                    graph = await graph
                if not hasattr(graph, "ainvoke"):
                    raise ValueError(
                        "Graph factory must return an async Runnable/compiled StateGraph"
                    )
                return graph
    return None
