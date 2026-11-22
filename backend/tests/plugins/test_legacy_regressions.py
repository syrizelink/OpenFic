"""Original Agent contracts must hold while an extension is enabled."""

import pytest

from app.agent_runtime.tools.registry import ToolRegistry
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")

TOOL_PLUGIN = """
async def echo(context, params):
    return "echo"
def register(host):
    host.register_tool("echo", "Echo", {"type":"object"}, echo, category="测试工具", display_name="回声", access_level="readonly")
"""


async def enable_probe(host):
    await host.install(
        host_tests.package(backend=TOOL_PLUGIN, capabilities=["agent.tools"])
    )
    await host.set_enabled("project-statistics", True)


async def test_explicit_empty_tool_selection_stays_empty_with_enabled_plugin(
    plugin_api,
):
    host, _, _ = plugin_api
    await enable_probe(host)
    assert ToolRegistry.get_tools(names=[], state={}) == []


async def test_explicit_builtin_selection_does_not_gain_plugin_tools(plugin_api):
    host, _, _ = plugin_api
    await enable_probe(host)
    tools = ToolRegistry.get_tools(names=["read_chapter"], state={})
    assert [tool.name for tool in tools] == ["read_chapter"]


async def test_selected_plugin_tool_receives_existing_build_hooks(plugin_api):
    host, _, _ = plugin_api
    await enable_probe(host)

    def customize(tool):
        tool.description = "Existing build hook applied"

    tools = ToolRegistry.get_tools(
        names=["plugin_project_statistics_echo"], state={}, build_hooks=[customize]
    )
    assert len(tools) == 1
    assert tools[0].description == "Existing build hook applied"


async def test_all_agents_require_explicit_plugin_tool_selection(plugin_api):
    from app.plugins.runtime import plugin_tool_names_for_agent
    from app.agent_runtime.graph.orchestrator.graph import _primary_tool_names

    host, _, _ = plugin_api
    await enable_probe(host)
    name = "plugin_project_statistics_echo"
    assert plugin_tool_names_for_agent() == []
    assert plugin_tool_names_for_agent({"plugin_tools": []}) == []
    assert plugin_tool_names_for_agent({"plugin_tools": [name]}) == [name]
    assert name not in await _primary_tool_names(None, "build")
    assert name not in await _primary_tool_names(None, "plan")


async def test_plugin_tools_are_listed_with_description_and_follow_lifecycle(plugin_api):
    from app.api.routers.agent_runtime import router as agent_router

    host, client, app = plugin_api
    app.include_router(agent_router, prefix="/api/v1/agent")
    await enable_probe(host)
    response = await client.get("/api/v1/agent/tools")
    assert response.status_code == 200
    tool = next(item for item in response.json() if item["key"] == "plugin_project_statistics_echo")
    assert tool["display_name"] == "回声"
    assert tool["category"] == "测试工具"
    assert tool["plugin_id"] == "project-statistics"
    assert tool["plugin_name"] == host.get("project-statistics").manifest.name
    assert tool["description"] == "Echo"
    assert tool["is_readonly"] is True
    await host.set_enabled("project-statistics", False)
    response = await client.get("/api/v1/agent/tools")
    assert all(item["key"] != "plugin_project_statistics_echo" for item in response.json())
    await host.set_enabled("project-statistics", True)
    response = await client.get("/api/v1/agent/tools")
    assert any(item["key"] == "plugin_project_statistics_echo" for item in response.json())


async def test_plugin_tool_sources_are_distinct_in_shared_category(plugin_api):
    from app.api.routers.agent_runtime import router as agent_router
    from test_host import package

    host, client, app = plugin_api
    app.include_router(agent_router, prefix="/api/v1/agent")
    await enable_probe(host)
    await host.install(package(plugin_id="other-source", backend=TOOL_PLUGIN, capabilities=["agent.tools"]))
    await host.set_enabled("other-source", True)
    host.get("other-source").manifest.name = "另一个插件"
    response = await client.get("/api/v1/agent/tools")
    assert response.status_code == 200
    tools = {item["key"]: item for item in response.json() if item.get("category") == "测试工具"}
    assert tools["plugin_project_statistics_echo"]["plugin_id"] == "project-statistics"
    assert tools["plugin_project_statistics_echo"]["plugin_name"] == host.get("project-statistics").manifest.name
    assert tools["plugin_other_source_echo"]["plugin_id"] == "other-source"
    assert tools["plugin_other_source_echo"]["plugin_name"] == "另一个插件"


async def test_agent_definition_controls_plugin_tools(plugin_api, session):
    from app.api.routers.agent_definitions import router as definition_router
    from app.agent_runtime.graph.orchestrator.graph import _primary_tool_names

    host, client, app = plugin_api
    app.include_router(definition_router, prefix="/api/v1")
    await enable_probe(host)
    name = "plugin_project_statistics_echo"
    config = {"configurable": {"db_session": session}}
    assert name not in await _primary_tool_names(config, "build")
    assert name not in await _primary_tool_names(config, "plan")

    response = await client.put("/api/v1/agent-definitions/build", json={"metadata": {"plugin_tools": [name]}})
    assert response.status_code == 200
    assert name in await _primary_tool_names(config, "build")
    response = await client.put("/api/v1/agent-definitions/build", json={"metadata": {"plugin_tools": []}})
    assert response.status_code == 200
    assert name not in await _primary_tool_names(config, "build")
    response = await client.put("/api/v1/agent-definitions/plan", json={"metadata": {"plugin_tools": [name]}})
    assert response.status_code == 200
    assert name in await _primary_tool_names(config, "plan")
    await host.set_enabled("project-statistics", False)
    assert name not in await _primary_tool_names(config, "plan")
    await host.set_enabled("project-statistics", True)
    assert name in await _primary_tool_names(config, "plan")


async def test_observer_hooks_preserve_original_message_metadata_and_tool_status(
    plugin_api, session
):
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )
    from app.plugins.runtime import model_messages

    host, _, _ = plugin_api
    await host.install(
        host_tests.package(
            backend="""
async def observe(context, event, next):
    return await next(event)
def register(host):
    host.register_hook("context.build", observe)
""",
            capabilities=["agent.hooks"],
        )
    )
    await host.set_enabled("project-statistics", True)
    messages = [
        SystemMessage(
            content="rules",
            name="system-rules",
            id="sys-1",
            additional_kwargs={"cache_control": "ephemeral"},
            response_metadata={"openfic_context": {"part": "rules"}},
        ),
        HumanMessage(
            content=[
                {"type": "text", "text": "attachment"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AAAA"},
                },
            ],
            id="user-1",
        ),
        AIMessage(
            content="",
            id="ai-1",
            tool_calls=[{"id": "call-1", "name": "read_chapter", "args": {}}],
            usage_metadata={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        ),
        ToolMessage(
            content="not found",
            name="read_chapter",
            tool_call_id="call-1",
            status="error",
            artifact={"source": "original-tool"},
        ),
    ]
    actual = await model_messages(messages, session, host=host)
    assert [m.model_dump() for m in actual] == [m.model_dump() for m in messages]


async def test_observer_hooks_preserve_structured_builtin_tool_results(plugin_api):
    from app.plugins.runtime import dispatch
    from app.agent_runtime.tools.errors import ToolResult

    host, _, _ = plugin_api
    await host.install(
        host_tests.package(
            backend="""
async def observe(context, event, next):
    return await next(event)
def register(host):
    host.register_hook("tool.call", observe)
    host.register_hook("tool.result", observe)
""",
            capabilities=["agent.hooks"],
        )
    )
    await host.set_enabled("project-statistics", True)
    original = ToolResult(
        "chapter content", {"type": "chapter", "data": {"content": "original"}}
    )

    async def execute(event):
        return {"result": original}

    result = await dispatch(
        "tool.call", {"tool": "read_chapter", "input": {}}, host=host, terminal=execute
    )
    result = await dispatch(
        "tool.result", {"tool": "read_chapter", "result": result["result"]}, host=host
    )
    assert isinstance(result["result"], ToolResult)
    assert result["result"] == original
    assert result["result"].payload == original.payload
    result["result"].payload["data"]["content"] = "changed"
    assert original.payload["data"]["content"] == "original"
