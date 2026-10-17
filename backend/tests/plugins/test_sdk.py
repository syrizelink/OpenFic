"""Public SDK contracts through business APIs and original Claude Mod packages."""

import io
import json
import zipfile

import httpx
import pytest
from langchain_core.messages import SystemMessage, HumanMessage

from app.plugins.host import PluginError
from app.plugins.runtime import dispatch, model_messages, plugin_tools
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api

pytestmark = pytest.mark.asyncio(loop_scope="module")


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
                    "backend": "backend/main.py",
                    **manifest,
                }
            ),
        )
        archive.writestr("backend/main.py", backend)
        for name, content in (files or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


async def test_business_crud_catalogue_validation_and_capabilities(plugin_api, session):
    host, _, _ = plugin_api
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
    assert any(event["event"] == "data.changed" for event in host.events()["events"])


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


async def test_secret_settings_are_encrypted_and_redacted(plugin_api):
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
    assert "hidden-setting" not in (host.root / ".registry.json").read_text()
    assert host.describe(host.get("sdk-test"))["configuration"]["token"] == ""
    await host.close()
    await host.start()
    assert host.get("sdk-test").settings["token"] == "hidden-setting"
    await host.configure("sdk-test", {"token": ""})
    assert host.get("sdk-test").settings["token"] == "hidden-setting"


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
    host.register_tool("echo","Echo",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},echo,access_level="readonly")
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


def mod_bundle(source):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            ".claude-plugin/plugin.json",
            json.dumps(
                {
                    "name": "demo-mod",
                    "version": "1.0.0",
                    "userConfig": {"suffix": {"type": "string", "default": "!"}},
                }
            ),
        )
        archive.writestr(
            "hooks/hooks.json", json.dumps({"modules": ["./register.tsx"]})
        )
        archive.writestr("hooks/register.tsx", source)
    return output.getvalue()


async def test_claude_mod_typescript_jsx_commands_ui_and_true_next(plugin_api, session):
    host, _, _ = plugin_api
    source = """
import type { On } from 'claude-code';
let count: number = 0;
export function register(on: On, options: {suffix:string}) {
  on('session.start', async ($,e,next) => { await $.command.register({name:'hello',description:'Hello'}); return next(e); });
  on('command.run',{command:'hello'}, async ($,e,next) => {count++; await $.store.set('count',count);return {text:'Hello'+options.suffix};});
  on('prompt.submit', async ($,e,next) => next({...e,text:e.text+options.suffix}));
  on('tool.call', async ($,e,next) => {const result=await next(e);return {result:result.result+' post'};});
  on('ui.render',{component:'Pane'},async ($,e,next) => {const {Box,Text,Button}=$.ui.resolve(e);return <Box><Text>Count: {count}</Text><Button label="Increment" onPress={()=>{count++}} /></Box>;});
  on('unsupported.event',async ($,e,next)=>next(e));
}
"""
    assert (await host.install(mod_bundle(source)))["format"] == "claude-mod"
    await host.set_enabled("demo-mod", True)
    assert (
        "Unsupported event: unsupported.event"
        in host.get("demo-mod").manifest.compatibility["warnings"]
    )
    assert (await host.call("demo-mod", "mod.command", {"command": "hello"}, session))[
        "text"
    ] == "Hello!"
    assert await host.context("demo-mod", session).storage.get("count") == 1
    assert (await dispatch("prompt.submit", {"text": "User"}, session, host=host))[
        "text"
    ] == "User!"

    async def terminal(event):
        return {"result": "actual"}

    assert await dispatch(
        "tool.call",
        {"tool": "read_chapter", "input": {}},
        session,
        host=host,
        terminal=terminal,
    ) == {"result": "actual post"}
    inspected = await host.call("demo-mod", "mod.inspect", {}, session)
    tree = next(t["tree"] for t in inspected["trees"] if t["component"] == "Pane")
    assert tree["type"] == "Box"
    action = tree["children"][1]["props"]["onPress"]
    await host.call("demo-mod", "mod.action", {"id": action}, session)
    inspected = await host.call("demo-mod", "mod.inspect", {}, session)
    assert "2" in json.dumps(inspected["trees"])
    await host.set_enabled("demo-mod", False)
    assert (await dispatch("prompt.submit", {"text": "User"}, session, host=host))[
        "text"
    ] == "User"


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


async def test_mod_cpu_limit_and_unsupported_node_import(plugin_api, session):
    host, _, _ = plugin_api
    await host.install(
        mod_bundle(
            "export function register(on) {on('command.run',async()=>{while(true){}})}"
        )
    )
    await host.set_enabled("demo-mod", True)
    with pytest.raises(PluginError, match="interrupted"):
        await host.call("demo-mod", "mod.command", {"command": "loop"}, session)
    await host.uninstall("demo-mod")
    await host.install(
        mod_bundle(
            "import fs from 'node:fs'; export function register(on){fs.readFileSync('/etc/passwd')}"
        )
    )
    with pytest.raises(PluginError, match="Unsupported module"):
        await host.set_enabled("demo-mod", True)
    assert host.describe(host.get("demo-mod"))["status"] == "error"
