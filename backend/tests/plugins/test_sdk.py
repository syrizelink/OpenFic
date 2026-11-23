"""Public native plugin SDK contracts through business APIs."""

import io
import html
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import quote

import httpx
import pytest
from langchain_core.messages import SystemMessage, HumanMessage

from app.plugins.host import PluginError
from app.plugins.runtime import dispatch, expand_quotes, model_messages, plugin_tools
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_quote_prompt_is_applied_only_to_its_own_message(monkeypatch):
    from app.agent_runtime.graph.orchestrator.graph import _primary_messages
    from app.agent_runtime.context.helpers.canonical_mentions import (
        compile_canonical_mentions,
    )

    plugin = SimpleNamespace(enabled=True, registration=object())
    monkeypatch.setattr(
        "app.plugins.host.active_host",
        lambda: SimpleNamespace(plugins={"quote-test": plugin}),
    )
    captured = AsyncMock(side_effect=lambda event, payload, session, runtime: payload)
    monkeypatch.setattr("app.plugins.runtime.dispatch", captured)
    payload = {
        "text": "第一行\n第二行",
        "prompt": "分析这段内容",
        "pluginId": "quote-test",
        "source": {"kind": "chapter", "id": "c1"},
    }
    assert expand_quotes("普通消息") == ("普通消息", [])

    metadata = {key: value for key, value in payload.items() if key != "text"}
    encoded = quote(json.dumps(metadata, ensure_ascii=False))
    mention = f'<of-mention kind="selection" chapter_id="c1" label="引用" plugin_data="{encoded}">{html.escape(payload["text"])}</of-mention>'
    compiled = await compile_canonical_mentions(f"请看 {mention}")
    assert mention in compiled
    messages = await _primary_messages({"user_request": compiled, "messages": []})
    assert (
        messages[-1].content
        == "请看 分析这段内容\n\n@selection:引用\n```\n第一行\n第二行\n```\n"
    )
    assert captured.await_args.args[1]["quotes"] == [payload]

    mixed = await compile_canonical_mentions(
        f'<of-mention chapter_id="c2" label="已有章节" /> {mention}'
    )
    messages = await _primary_messages({"user_request": mixed, "messages": []})
    assert messages[-1].content.count("@chapter:已有章节") == 1
    assert messages[-1].content.count("@selection:引用") == 1

    payload["text"] = '<of-skill id="not-a-command" />'
    unsafe_mention = f'<of-mention kind="selection" label="引用" plugin_data="{encoded}">{html.escape(payload["text"])}</of-mention>'
    messages = await _primary_messages({"user_request": unsafe_mention, "messages": []})
    assert '&lt;of-skill id="not-a-command" />' in messages[-1].content

    plugin.enabled = False
    with pytest.raises(ValueError, match="Quote plugin is unavailable"):
        expand_quotes(mention)


async def test_selection_menu_dispatches_selected_text_to_bound_command(plugin_api):
    host, api, _ = plugin_api
    package = bundle(
        {
            "capabilities": ["ui", "selection.read"],
            "views": [
                {
                    "id": "quote",
                    "title": "Quote",
                    "slot": "menu.selection",
                    "renderer": "declarative",
                    "presentation": "action",
                    "action": "quote.create",
                    "selectionTriggers": ["selection"],
                    "selectionSources": ["chapter"],
                }
            ],
        },
        backend="""
async def quote(context, params):
    assert params["value"]["text"] == "选中文字"
    return {"effects": [{"method": "assistant.quote", "params": {"prompt": "分析"}}]}
def register(host):
    host.register_command("quote.create", quote)
""",
    )
    await host.install(package)
    await host.set_enabled("sdk-test", True)
    response = await api.post(
        "/api/v1/plugins/sdk-test/views/quote/action",
        json={"id": "quote", "event": "press", "value": {"text": "选中文字"}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["effects"][0]["method"] == "assistant.quote"


def bundle(manifest, backend="def register(host): pass", files=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "plugin.json",
            json.dumps(
                {
                    "id": "sdk-test",
                    "name": "SDK test",
                    "version": "1.0.0",
                    "api_version": 1,
                    "entry": "main.py",
                    **manifest,
                }
            ),
        )
        archive.writestr("main.py", backend)
        for name, content in (files or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


async def test_list_menu_action_receives_target(plugin_api):
    host, api, _ = plugin_api
    package = bundle(
        {
            "capabilities": ["ui"],
            "views": [
                {
                    "id": "inspect",
                    "title": "Inspect",
                    "slot": "menu.character",
                    "renderer": "declarative",
                    "presentation": "action",
                    "action": "inspect",
                }
            ],
        },
        "def register(host):\n    host.register_command('inspect', lambda context, params: params['context']['menuTarget'])\n",
    )
    await host.install(package)
    await host.set_enabled("sdk-test", True)
    target = {"kind": "menu.character", "ids": ["c1", "c2"], "projectId": "p1"}
    response = await api.post(
        "/api/v1/plugins/sdk-test/views/inspect/action",
        json={
            "id": "inspect",
            "event": "press",
            "value": target,
            "context": {"projectId": "p1", "menuTarget": target},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"] == target


async def test_business_crud_catalogue_validation_and_capabilities(
    plugin_api, session, monkeypatch
):
    host, _, _ = plugin_api
    send = AsyncMock()
    monkeypatch.setattr("app.socket.emitter.emit", send)
    await host.install(
        bundle(
            {
                "capabilities": [
                    "projects.read",
                    "projects.write",
                    "chapters.read",
                    "chapters.write",
                    "volumes.read",
                    "notes.read",
                    "notes.write",
                    "events",
                ]
            }
        )
    )
    await host.set_enabled("sdk-test", True)
    ctx = host.context("sdk-test", session)
    project = await ctx.projects.create({"title": "SDK project"})
    volumes = await ctx.resource("volumes").list(project["id"])
    chapter = await ctx.chapters.create(
        {"title": "One", "volume_id": volumes[0]["id"], "content": "hello"},
        project["id"],
    )
    updated = await ctx.chapters.update(
        chapter["id"], {"content": "updated", "word_count": 7}
    )
    assert updated["content"] == "updated"
    assert (await ctx.chapters.get(chapter["id"]))["word_count"] == 7
    note = await ctx.notes.create(
        {"title": "Note", "content": "private"}, project["id"]
    )
    assert (await ctx.notes.get(note["id"]))["content"] == "private"
    await ctx.notes.delete(note["id"])
    with pytest.raises(ValueError, match="404"):
        await ctx.notes.get(note["id"])
    with pytest.raises(PermissionError, match="characters.read"):
        await ctx.api.request("GET", f"/projects/{project['id']}/characters")
    for path in [
        "https://example.com",
        "//host/path",
        "/chapters/../settings",
        "/plugins",
        "/auth/login",
    ]:
        with pytest.raises((ValueError, PermissionError)):
            await ctx.api.request("GET", path)
    with pytest.raises(ValueError, match="422"):
        await ctx.chapters.update(chapter["id"], {"title": ""})
    assert (await ctx.chapters.get(chapter["id"]))["title"] == "One"
    from app.plugins.gateway import BusinessAPI

    catalogue = BusinessAPI.catalogue()
    assert len(catalogue["operations"]) > 180
    assert "/chapters/{chapter_id}" in catalogue["openapi"]["paths"]
    assert any(
        operation["path"] == "/agent/sessions" for operation in catalogue["operations"]
    )
    await host._notifications.join()
    assert any(
        call.args[0] == "plugins:event" and call.args[1]["event"] == "data.changed"
        for call in send.await_args_list
    )


async def test_storage_secrets_files_network_and_disable(plugin_api, session):
    host, _, _ = plugin_api
    await host.install(
        bundle(
            {
                "capabilities": ["storage", "secrets", "files", "network"],
                "network_hosts": ["api.example.com"],
            }
        )
    )
    await host.set_enabled("sdk-test", True)
    ctx = host.context("sdk-test", session)
    await ctx.storage.set("test", {"value": 3})
    assert await ctx.storage.get("test") == {"value": 3}
    await ctx.secrets.set("token", "super-private-token")
    assert (
        "super-private-token"
        not in (host.root / ".data/sdk-test/secrets.json").read_text()
    )
    assert await ctx.secrets.get("token") == "super-private-token"
    with pytest.raises(PluginError, match="Secrets cannot be read"):
        await host.call("sdk-test", "sdk.secrets.get", {"key": "token"}, session)
    await ctx.files.write("nested/test.txt", "data")
    assert await ctx.files.read("nested/test.txt") == "data"
    with pytest.raises(ValueError):
        await ctx.files.read("../secrets.json")

    async def remote(request):
        return httpx.Response(200, json={"ok": True})

    host.http_transport = httpx.MockTransport(remote)
    assert (await ctx.http.request("GET", "https://api.example.com/data"))["json"] == {
        "ok": True
    }
    with pytest.raises(PermissionError):
        await ctx.http.request("GET", "https://other.example.com")
    await host.close()
    await host.start()
    assert await host.context("sdk-test", session).storage.get("test") == {"value": 3}
    assert (
        await host.context("sdk-test", session).secrets.get("token")
        == "super-private-token"
    )
    await host.uninstall("sdk-test")
    assert not (host.root / ".data/sdk-test").exists()


async def test_provider_api_key_requires_separate_permission_and_rejects_oauth(
    plugin_api, session
):
    from app.core.encryption import EncryptionService
    from app.models.entities.model_provider import ModelProvider
    from app.settings import settings

    host, _, _ = plugin_api
    cipher = EncryptionService(settings.encryption_key)
    key = "provider-private-key-for-sdk-test"
    provider = ModelProvider(
        id="provider-key",
        name="API",
        url="https://example.com",
        provider_type="openai",
        api_key_encrypted=cipher.encrypt(key),
    )
    no_key = ModelProvider(
        id="provider-empty",
        name="Empty",
        url="https://example.com",
        provider_type="openai",
        api_key_encrypted="",
    )
    oauth = ModelProvider(
        id="provider-oauth",
        name="OAuth",
        url="https://example.com",
        provider_type="openai-codex",
        api_key_encrypted=cipher.encrypt(key),
    )
    other_oauth = ModelProvider(
        id="provider-grant",
        name="Grant",
        url="https://example.com",
        provider_type="openai-compatible",
        api_key_encrypted=cipher.encrypt(key),
        credentials_encrypted="opaque-oauth-grant",
    )
    session.add_all([provider, no_key, oauth, other_oauth])
    await session.flush()
    await host.install(bundle({"id": "sdk-denied", "capabilities": ["providers.read"]}))
    await host.set_enabled("sdk-denied", True)
    denied = host.context("sdk-denied", session)
    assert key not in json.dumps(await denied.api.request("GET", "/model-providers"))
    with pytest.raises(PermissionError, match="credentials.read"):
        await denied.providers.get_credential(provider.id)

    source = """
async def reveal(ctx, params):
    return await ctx.providers.get_credential(params["provider_id"])
def register(host):
    host.register_command("reveal", reveal)
"""
    await host.install(bundle({"capabilities": ["credentials.read"]}, source))
    await host.set_enabled("sdk-test", True)
    ctx = host.context("sdk-test", session)
    assert await ctx.providers.get_credential(provider.id) == key
    assert await ctx.providers.get_credential(no_key.id) is None
    with pytest.raises(ValueError, match="not found"):
        await ctx.providers.get_credential("does-not-exist")
    for blocked in (oauth, other_oauth):
        with pytest.raises(ValueError, match="OAuth"):
            await ctx.providers.get_credential(blocked.id)
    with pytest.raises(PluginError, match="Unsupported SDK method"):
        await host.call(
            "sdk-test",
            "sdk.providers.get_credential",
            {"provider_id": provider.id},
            session,
        )

    assert (
        await host.call("sdk-test", "reveal", {"provider_id": provider.id}, session)
        == key
    )
    provider.api_key_encrypted = cipher.encrypt("rotated-sdk-test-key")
    await session.flush()
    assert await ctx.providers.get_credential(provider.id) == "rotated-sdk-test-key"


async def test_secret_settings_are_encrypted_and_redacted(plugin_api):
    from app.plugins.host import redact_plugin_error

    host, _, _ = plugin_api
    await host.install(
        bundle(
            {
                "settings": [
                    {
                        "key": "token",
                        "label": "Token",
                        "type": "string",
                        "default": "",
                        "secret": True,
                    }
                ]
            }
        )
    )
    await host.configure("sdk-test", {"token": "hidden-setting"})
    message = redact_plugin_error(
        '{"password":"other-secret","detail":"hidden-setting"}', host.get("sdk-test")
    )
    assert "hidden-setting" not in message
    assert "other-secret" not in message
    assert "hidden-setting" not in (host.root / ".registry.json").read_text()
    assert host.describe(host.get("sdk-test"))["configuration"]["token"] == ""
    await host.close()
    await host.start()
    assert host.get("sdk-test").settings["token"] == "hidden-setting"
    await host.configure("sdk-test", {"token": ""})
    assert host.get("sdk-test").settings["token"] == "hidden-setting"


async def test_plugin_tool_requires_nonempty_category_and_display_name():
    from app.plugins.host import Registration

    async def handler(ctx, params):
        return None

    registry = Registration()
    with pytest.raises(TypeError):
        registry.register_tool("echo", "Echo", {"type": "object"}, handler)
    with pytest.raises(TypeError):
        registry.register_tool(
            "echo", "Echo", {"type": "object"}, handler, category="测试工具"
        )
    with pytest.raises(TypeError):
        registry.register_tool(
            "echo", "Echo", {"type": "object"}, handler, display_name="回声"
        )
    for category, display_name in (
        ("", "回声"),
        (" ", "回声"),
        (None, "回声"),
        ("测试工具", ""),
        ("测试工具", " "),
        ("测试工具", None),
    ):
        with pytest.raises(ValueError, match="category.*display_name"):
            registry.register_tool(
                "echo",
                "Echo",
                {"type": "object"},
                handler,
                category=category,
                display_name=display_name,
            )
    registry.register_tool(
        "echo",
        "Echo",
        {"type": "object"},
        handler,
        category=" 测试工具 ",
        display_name=" 回声 ",
    )
    assert registry.tools["echo"]["category"] == "测试工具"
    assert registry.tools["echo"]["display_name"] == "回声"
    for extra in (
        {"title": " "},
        {"icon": "NotALucideIcon"},
        {"icon": "../bad.svg"},
        {"detail": {}},
    ):
        with pytest.raises(ValueError):
            registry.register_tool(
                "other",
                "Echo",
                {"type": "object"},
                handler,
                category="测试",
                display_name="回声",
                **extra,
            )
    registry.register_tool(
        "fixed",
        "Echo",
        {"type": "object"},
        handler,
        category="测试",
        display_name="回声",
        detail="a" * 1100,
    )
    assert len(registry.tools["fixed"]["detail"]) == 1024


async def test_plugin_tool_presentation_is_per_call_and_preserves_result(
    plugin_api, session
):
    from app.agent_runtime.runner.event_translator import EventTranslator
    from app.agent_runtime.tools.errors import ToolResult

    host, api, app = plugin_api
    source = """
async def echo(ctx, params): return {"echo": params["text"], "success": True}
def detail(args, result): return f"{args['text']} → {result['echo']}"
def register(host):
    host.register_tool("echo", "Echo", {"type":"object", "properties":{"text":{"type":"string"}}}, echo,
        category="测试", display_name="回声", icon="CloudUpload", title="同步中", detail=detail, access_level="readonly")
"""
    await host.install(bundle({"capabilities": ["agent.tools"]}, source))
    await host.set_enabled("sdk-test", True)
    from app.api.routers.agent_runtime import router as agent_router

    app.include_router(agent_router, prefix="/api/v1/agent")
    listing = (await api.get("/api/v1/agent/tools")).json()
    metadata = next(item for item in listing if item["key"] == "plugin_sdk_test_echo")
    assert metadata["title"] == "同步中" and metadata["icon"] == "CloudUpload"
    assert "detail" not in metadata
    tool = plugin_tools({"project_id": "project", "session_id": "session"})[0]
    events = [
        event
        async for event in tool.astream_events(
            {"text": "甲"},
            config={"configurable": {"db_session": session}},
            version="v2",
        )
    ]
    end = next(event for event in events if event["event"] == "on_tool_end")
    result = end["data"]["output"]
    assert isinstance(result, ToolResult)
    assert json.loads(result) == {"echo": "甲", "success": True}
    assert result.payload["_openfic_plugin_tool"] == {
        "plugin_id": "sdk-test",
        "icon": "CloudUpload",
        "title": "同步中",
        "detail": "甲 → 甲",
    }
    translated = EventTranslator(session_id="session").translate(end)
    assert (
        translated["data"]["plugin_tool_display"]
        == result.payload["_openfic_plugin_tool"]
    )
    assert json.loads(translated["data"]["output"]) == {"echo": "甲", "success": True}
    second = await tool.ainvoke(
        {"text": "乙"}, config={"configurable": {"db_session": session}}
    )
    assert second.payload["_openfic_plugin_tool"]["detail"] == "乙 → 乙"

    async def async_detail(args, result):
        return f"异步 {result['echo']}"

    host.get("sdk-test").registration.tools["echo"]["detail"] = async_detail
    third = await tool.ainvoke(
        {"text": "丙"}, config={"configurable": {"db_session": session}}
    )
    assert third.payload["_openfic_plugin_tool"]["detail"] == "异步 丙"

    def broken_detail(args, result):
        raise ValueError("private-data-should-not-be-logged")

    host.get("sdk-test").registration.tools["echo"]["detail"] = broken_detail
    failed_detail = await tool.ainvoke(
        {"text": "丁"}, config={"configurable": {"db_session": session}}
    )
    assert json.loads(failed_detail) == {"echo": "丁", "success": True}
    assert failed_detail.payload["_openfic_plugin_tool"]["detail"] is None
    assert "private-data-should-not-be-logged" not in json.dumps(host.logs("sdk-test"))


async def test_plugin_tool_asset_icon_requires_valid_public_resource(plugin_api):
    host, api, _ = plugin_api
    source = """
async def echo(ctx, params): return "ok"
def register(host):
    host.register_tool("echo", "Echo", {"type": "object"}, echo,
        category="测试", display_name="回声", icon="assets/icon.svg")
"""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><path d="M0 0h10v10z"/></svg>'
    await host.install(
        bundle(
            {"capabilities": ["agent.tools"], "resources": ["assets"]},
            source,
            {"assets/icon.svg": svg},
        )
    )
    await host.set_enabled("sdk-test", True)
    assert plugin_tools({})[0].icon == "assets/icon.svg"
    response = await api.get(
        "/api/v1/plugins/sdk-test/status-icon", params={"path": "assets/icon.svg"}
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "image/svg+xml"
    )
    await host.install(
        bundle(
            {"id": "bad-icon", "capabilities": ["agent.tools"]},
            source.replace("assets/icon.svg", "NotALucideIcon"),
        )
    )
    with pytest.raises(PluginError, match="Unknown Lucide icon"):
        await host.set_enabled("bad-icon", True)
    await host.install(
        bundle(
            {"id": "private-icon", "capabilities": ["agent.tools"]},
            source,
            {"assets/icon.svg": svg},
        )
    )
    with pytest.raises(PluginError, match="declared public resource"):
        await host.set_enabled("private-icon", True)
    unsafe = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    await host.install(
        bundle(
            {
                "id": "unsafe-icon",
                "capabilities": ["agent.tools"],
                "resources": ["assets"],
            },
            source,
            {"assets/icon.svg": unsafe},
        )
    )
    with pytest.raises(PluginError, match="Invalid plugin tool icon"):
        await host.set_enabled("unsafe-icon", True)


async def test_plugin_tool_presentation_survives_graph_execution(plugin_api, session):
    from unittest.mock import patch
    from langchain_core.messages import AIMessage, ToolMessage
    from app.agent_runtime.graph.react_agent import create_react_agent
    from app.agent_runtime.types import ReactAgentConfig, TerminationCondition
    from app.agent_runtime.tools.errors import ToolResult

    host, _, _ = plugin_api
    source = """
async def echo(ctx, params): return {"success": True, "echo": params["text"]}
def detail(args, result): return f"已处理 {result['echo']}"
def register(host):
    host.register_tool("echo", "Echo", {"type": "object", "properties": {"text": {"type": "string"}}}, echo,
        category="测试", display_name="回声", detail=detail, access_level="readonly")
"""
    await host.install(bundle({"capabilities": ["agent.tools"]}, source))
    await host.set_enabled("sdk-test", True)
    tool = plugin_tools({"project_id": "project", "session_id": "session"})[0]
    graph = create_react_agent(
        ReactAgentConfig(
            name="test",
            tools=[tool],
            termination=TerminationCondition(mode="tool_success", tool_name=tool.name),
        )
    )
    model_result = AIMessage(
        content="",
        tool_calls=[{"id": "call_graph", "name": tool.name, "args": {"text": "内容"}}],
    )
    tool_events = []
    final_state = None
    with (
        patch(
            "app.agent_runtime.graph.react_agent._invoke_model",
            new=AsyncMock(return_value=model_result),
        ),
        patch(
            "app.agent_runtime.graph.react_agent.build_context",
            new=AsyncMock(return_value=[HumanMessage(content="test")]),
        ),
    ):
        async for event in graph.astream_events(
            {
                "messages": [HumanMessage(content="test")],
                "iteration_count": 0,
                "is_done": False,
                "final_output": None,
            },
            config={"configurable": {"db_session": session}},
            version="v2",
        ):
            if event["event"] == "on_tool_end" and event["name"] == tool.name:
                tool_events.append(event)
            if event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                final_state = event["data"]["output"]
    result = tool_events[0]["data"]["output"]
    assert isinstance(result, ToolResult)
    assert result.payload["_openfic_plugin_tool"]["detail"] == "已处理 内容"
    assert final_state is not None
    message = next(
        item for item in final_state["messages"] if isinstance(item, ToolMessage)
    )
    assert json.loads(message.content) == {"success": True, "echo": "内容"}
    assert "_openfic_plugin_tool" not in message.content


async def test_native_tool_and_prompt_middleware_are_live_and_disposed(
    plugin_api, session
):
    host, _, _ = plugin_api
    source = """
async def echo(ctx, params): return {"echo":params["text"]}
async def hook(ctx,event,next):
    event["sections"].append({"id":"extra","text":"injected","scope":"system"})
    return await next(event)
def register(host):
    host.register_tool("echo","Echo",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},echo,category="测试工具",display_name="回声",access_level="readonly")
    host.register_hook("prompt.compose",hook)
"""
    await host.install(bundle({"capabilities": ["agent.tools", "agent.hooks"]}, source))
    await host.set_enabled("sdk-test", True)
    tools = plugin_tools({"project_id": "project", "session_id": "session"})
    assert len(tools) == 1
    result = await tools[0].ainvoke(
        {"text": "hello"}, config={"configurable": {"db_session": session}}
    )
    assert json.loads(result) == {"echo": "hello"}
    messages = await model_messages(
        [SystemMessage("base"), HumanMessage("user")], session, host=host
    )
    assert [m.content for m in messages] == ["base", "injected", "user"]
    await host.set_enabled("sdk-test", False)
    assert not plugin_tools({})


async def test_hook_order_uses_plugin_order_after_explicit_priority(
    plugin_api, session
):
    host, _, _ = plugin_api
    source = """
async def hook(ctx, event, next):
    event['order'].append(ctx.plugin_id)
    return await next(event)
def register(host):
    host.register_hook('prompt.compose', hook, priority=PRIORITY)
"""
    for plugin_id, priority in [("alpha", 0), ("zeta", 0), ("early", -10)]:
        await host.install(
            bundle(
                {"id": plugin_id, "capabilities": ["agent.hooks"]},
                source.replace("PRIORITY", str(priority)),
            )
        )
        await host.set_enabled(plugin_id, True)
    await host.set_order(["zeta", "early", "alpha"])
    result = await dispatch("prompt.compose", {"order": []}, session, host=host)
    assert result["order"] == ["early", "zeta", "alpha"]
    await host.set_order(["alpha", "early", "zeta"])
    result = await dispatch("prompt.compose", {"order": []}, session, host=host)
    assert result["order"] == ["early", "alpha", "zeta"]


async def test_hook_order_reentry_and_read_only_editor_observer(plugin_api, session):
    host, _, _ = plugin_api
    observer = """
async def observe(ctx,event,next): return await next(event)
def register(host): host.register_hook('editor.change',observe,priority=-10)
"""
    writer = """
async def first(ctx,event,next):
    event['content'] += ' first'
    return await next(event)
async def second(ctx,event,next):
    event['content'] += ' second'
    return await next(event)
def register(host):
    host.register_hook('editor.change',first)
    host.register_hook('editor.change',second)
"""
    await host.install(
        bundle(
            {"id": "observer", "capabilities": ["agent.hooks", "editor.read"]}, observer
        )
    )
    await host.install(
        bundle(
            {
                "id": "writer",
                "capabilities": ["agent.hooks", "editor.read", "editor.write"],
            },
            writer,
        )
    )
    await host.set_enabled("observer", True)
    await host.set_enabled("writer", True)
    result = await dispatch(
        "editor.change", {"id": "chapter", "content": "text"}, session, host=host
    )
    assert result["content"] == "text first second"


async def test_editor_mutation_requires_write_capability(plugin_api, session):
    host, _, _ = plugin_api
    source = """
async def edit(ctx,event,next): return await next({**event,'content':'overwrite'})
def register(host): host.register_hook('editor.change',edit)
"""
    await host.install(bundle({"capabilities": ["agent.hooks", "editor.read"]}, source))
    await host.set_enabled("sdk-test", True)
    with pytest.raises(PermissionError, match="editor.write"):
        await dispatch("editor.change", {"content": "original"}, session, host=host)


async def test_public_agent_tool_call_retains_runtime_approval_and_provenance(
    plugin_api, session, monkeypatch
):
    from app.agent_runtime.tools.base import AgentTool
    from app.agent_runtime.tools import ToolRegistry
    from pydantic import BaseModel

    host, _, _ = plugin_api
    await host.install(bundle({"capabilities": ["agent.invoke"]}))
    await host.set_enabled("sdk-test", True)
    observed = {}
    from app.agent_runtime.tools.hooks import auth

    original_auth = auth.auth_hook

    async def check_nested_approval(context):
        observed["approval_args"] = context.args
        return await original_auth(context)

    monkeypatch.setattr(auth, "auth_hook", check_nested_approval)

    class Arguments(BaseModel):
        text: str

    class RevisionAwareTool(AgentTool):
        name: str = "sdk_revision_test"
        access_level: str = "readonly"
        args_schema: type[BaseModel] = Arguments

        async def _execute(self, text):
            observed.update(
                state=self.runtime_state,
                config=self.config,
                tool_call_id=self.tool_call_id,
            )
            return json.dumps(
                {
                    "success": True,
                    "revision": self.runtime_state["current_revision_id"],
                    "text": text,
                }
            )

    monkeypatch.setitem(ToolRegistry._tools, "sdk_revision_test", RevisionAwareTool)
    ctx = host.context(
        "sdk-test",
        session,
        {
            "session_id": "session",
            "project_id": "project",
            "current_revision_id": "revision",
            "_tool_call_id": "outer-plugin-call",
            "_runnable_config": {
                "configurable": {"db_session": session},
                "metadata": {
                    "openfic_phase": "execute",
                    "openfic_skip_pre_hooks": True,
                    "tool_call": {"args": {"outer": True}},
                },
            },
        },
    )
    assert "_runnable_config" not in ctx.runtime
    assert any(t["name"] == "sdk_revision_test" for t in ctx.agent.tools())
    assert (await ctx.agent.call_tool("sdk_revision_test", {"text": "change"}))[
        "revision"
    ] == "revision"
    assert observed["tool_call_id"] == "outer-plugin-call"
    assert observed["approval_args"] == {"text": "change"}
    assert observed["config"]["callbacks"].handlers == []
    assert "openfic_skip_pre_hooks" not in observed["config"]["metadata"]
    assert "tool_call" not in observed["config"]["metadata"]
    with pytest.raises(ValueError, match="active versioned"):
        await host.context("sdk-test", session).agent.call_tool(
            "sdk_revision_test", {"text": "change"}
        )
