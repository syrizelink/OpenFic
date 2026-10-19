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
    host.register_tool("echo", "Echo", {"type":"object"}, echo, access_level="readonly")
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


async def test_default_build_opt_in_preserves_other_agents_scope(plugin_api):
    from app.plugins.runtime import plugin_tool_names_for_agent
    from app.agent_runtime.graph.orchestrator.graph import _primary_tool_names

    host, _, _ = plugin_api
    await enable_probe(host)
    name = "plugin_project_statistics_echo"
    assert plugin_tool_names_for_agent("build") == [name]
    assert plugin_tool_names_for_agent("explore") == []
    assert plugin_tool_names_for_agent("build", {"plugin_tools": []}) == []
    assert plugin_tool_names_for_agent("explore", {"plugin_tools": [name]}) == [name]
    assert name in await _primary_tool_names(None, "build")
    assert name not in await _primary_tool_names(None, "plan")


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
