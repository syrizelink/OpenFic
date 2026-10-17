"""Shared SDK dispatch and Agent middleware/graph/tool adaptation."""

import asyncio
import copy

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


async def sdk_call(context, method: str, params: dict):
    if method == "api.request":
        return await context.api.request(**params)
    if method == "catalogue":
        from app.plugins.gateway import BusinessAPI
        from app.plugins.manifest import CAPABILITIES, UI_SLOTS, SDK_VERSION

        return {
            "version": SDK_VERSION,
            "capabilities": sorted(CAPABILITIES),
            "slots": UI_SLOTS,
            "events": sorted(EVENTS),
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
        # Host-owned selector, deliberately outside plugin export/storage.
        from app.plugins.services import PluginStorage

        storage = PluginStorage(context.host, plugin)
        await storage.set(f"workflow:{project_id}", provider)
        return {"provider": f"{context.plugin_id}/{provider}" if provider else None}
    if method == "log":
        context.log(params["message"], params.get("level", "info"))
        return None
    raise ValueError(f"Unsupported SDK method: {method}")


async def dispatch(
    event: str, payload: dict, session=None, *, host=None, runtime=None, terminal=None
):
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
        context = host.context(plugin_id, session, runtime)
        called = False

        async def next_handler(value=None):
            nonlocal called
            if called:
                raise ValueError("Middleware next() may only be called once")
            called = True
            return await step(index + 1, data if value is None else value)

        async with asyncio.timeout(30):
            return await handler(context, copy.deepcopy(data), next_handler)

    return await step(0, payload)


async def model_messages(messages, session=None, *, runtime=None, host=None):
    """Runs on the final prompt, including transient and injected user messages."""
    from langchain_core.messages import convert_to_messages
    from app.plugins.host import active_host

    current = host or active_host()
    if current is None or not any(
        p.registration and p.registration.hooks for p in current.plugins.values()
    ):
        return messages

    data = [
        {
            "role": {"human": "user", "ai": "assistant"}.get(m.type, m.type),
            "content": m.content,
            **({"tool_call_id": m.tool_call_id} if m.type == "tool" else {}),
            **({"tool_calls": m.tool_calls} if m.type == "ai" and m.tool_calls else {}),
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
        {"id": f"system-{i}", "text": m["content"], "scope": "system"}
        for i, m in enumerate(base["messages"])
        if m["role"] == "system"
    ]
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
        if result.get("text") is not None:
            sections.append({"role": "system", "content": result["text"]})
    final = [*sections, *(m for m in base["messages"] if m["role"] != "system")]
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
    bounded_json(final, 8 * 1024 * 1024)
    return convert_to_messages(final)


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


async def selected_graph(state, config, model):
    from app.plugins.host import active_host
    from app.plugins.services import PluginStorage

    host = active_host()
    if host is None:
        return None
    for plugin in host.plugins.values():
        if (
            not plugin.registration
            or not plugin.registration.graphs
            or "storage" not in plugin.manifest.capabilities
        ):
            continue
        provider = await PluginStorage(host, plugin).get(
            f"workflow:{state.get('project_id')}"
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
