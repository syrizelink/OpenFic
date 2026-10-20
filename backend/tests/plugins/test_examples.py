"""Install example ZIPs and exercise real SDK paths and graph transitions."""

import io
import json
import zipfile
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.plugins.oauth import finish_oauth
from app.plugins.runtime import model_messages, plugin_tools, sdk_call, selected_graph
from tests.plugins import test_host as host_tests
from tests.plugins.fake_drive import FakeDrive

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")
SOURCE = Path(__file__).resolve().parents[3] / "examples/plugins"


def example_package(name):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((SOURCE / name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.writestr(
                    path.relative_to(SOURCE / name).as_posix(), path.read_bytes()
                )
    return output.getvalue()


async def setup_drive(host, session):
    await host.install(example_package("google-drive-sync"))
    await host.set_enabled("google-drive-sync", True)
    drive = FakeDrive()
    host.http_transport = httpx.MockTransport(drive)
    ctx = host.context("google-drive-sync", session)
    await ctx.secrets.set("oauth.tokens", {"access_token": "test-drive-token"})
    return ctx, drive


async def test_drive_two_way_conflict_resolution_and_agent_tool(
    plugin_api, client, session
):
    host, _, _ = plugin_api
    ctx, drive = await setup_drive(host, session)
    project = (
        await client.post("/api/v1/projects", data={"title": "Cloud sync"})
    ).json()
    volume = (await client.get(f"/api/v1/projects/{project['id']}/volumes")).json()[0]
    chapter = (
        await client.post(
            f"/api/v1/projects/{project['id']}/chapters",
            json={
                "title": "Chapter",
                "volume_id": volume["id"],
                "content": "initial",
                "word_count": 1,
            },
        )
    ).json()
    params = {"projectId": project["id"]}
    result = await host.call("google-drive-sync", "drive.sync", params, session)
    assert result["uploaded"] == 1 and len(drive.files) == 1
    file_id = next(iter(drive.files))
    assert drive.files[file_id]["payload"]["content"] == "initial"
    assert (await host.call("google-drive-sync", "drive.sync", params, session))[
        "unchanged"
    ] == 1
    drive.change(file_id, "remote change")
    assert (await host.call("google-drive-sync", "drive.sync", params, session))[
        "downloaded"
    ] == 1
    assert (await ctx.chapters.get(chapter["id"]))["content"] == "remote change"
    await ctx.chapters.update(chapter["id"], {"content": "local edit"})
    drive.change(file_id, "competing remote edit")
    report = await host.call("google-drive-sync", "drive.sync", params, session)
    assert len(report["conflicts"]) == 1
    assert (await ctx.chapters.get(chapter["id"]))["content"] == "local edit"
    assert drive.files[file_id]["payload"]["content"] == "competing remote edit"
    report = await host.call(
        "google-drive-sync",
        "drive.sync",
        {**params, "resolutions": {chapter["id"]: "remote"}},
        session,
    )
    assert report["downloaded"] == 1
    assert (await ctx.chapters.get(chapter["id"]))["content"] == "competing remote edit"
    tools = plugin_tools({"project_id": project["id"], "session_id": "test-session"})
    tool = next(t for t in tools if t.name.endswith("sync_chapters"))
    report = json.loads(
        await tool.ainvoke({}, config={"configurable": {"db_session": session}})
    )
    assert report["unchanged"] == 1
    assert all("googleapis.com" in url for _, url in drive.requests)


async def test_drive_oauth_pkce_replay_and_encrypted_tokens(plugin_api, session):
    host, _, _ = plugin_api
    ctx, _ = await setup_drive(host, session)
    await host.configure(
        "google-drive-sync",
        {"clientId": "client-id", "clientSecret": "client-secret", "folderId": ""},
    )
    result = await host.call(
        "google-drive-sync",
        "drive.connect",
        {},
        session,
        runtime={"backend_url": "http://test"},
    )
    query = parse_qs(urlsplit(result["url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://test/plugin-oauth/callback"]
    state = query["state"][0]
    await finish_oauth(host, state, "test-auth-code", None)
    assert any(event["event"] == "ui.invalidate" for event in host.events(0)["events"])
    assert (await ctx.secrets.get("oauth.tokens"))["refresh_token"] == "test-refresh"
    with pytest.raises(ValueError, match="already used"):
        await finish_oauth(host, state, "test-auth-code", None)
    assert (
        "test-drive-token"
        not in (host.root / ".data/google-drive-sync/secrets.json").read_text()
    )


async def test_handoff_graph_demo_native_selection_and_note(
    plugin_api, client, session
):
    host, _, _ = plugin_api
    await host.install(example_package("handoff-workflow"))
    await host.set_enabled("handoff-workflow", True)
    project = (await client.post("/api/v1/projects", data={"title": "Handoff"})).json()
    result = await host.call(
        "handoff-workflow",
        "workflow.run",
        {"projectId": project["id"], "prompt": "Write a story", "demo": True},
        session,
    )
    assert [(t["from"], t["to"]) for t in result["handoffs"]] == [
        ("planner", "writer"),
        ("writer", "reviewer"),
    ]
    assert result["rounds"] == 3 and "审核通过" in result["text"]
    ctx = host.context("handoff-workflow", session)
    await sdk_call(
        ctx, "workflow.select", {"projectId": project["id"], "provider": "handoff"}
    )
    graph = await selected_graph(
        {"project_id": project["id"], "demo": True},
        {"configurable": {"db_session": session}},
        None,
    )
    output = await graph.ainvoke(
        {
            "messages": [HumanMessage("Story")],
            "handoffs": [],
            "rounds": 0,
            "final_output": "",
        }
    )
    assert output["rounds"] == 3
    note = await ctx.notes.create(
        {"title": "Workflow output", "content": result["text"]}, project["id"]
    )
    assert note["content"] == result["text"]
    await sdk_call(
        ctx, "workflow.select", {"projectId": project["id"], "provider": None}
    )
    assert await selected_graph({"project_id": project["id"]}, None, None) is None


async def test_prompt_rules_preview_real_context_and_toggle(plugin_api, session):
    host, _, _ = plugin_api
    await host.install(example_package("prompt-elements"))
    await host.set_enabled("prompt-elements", True)
    original = [SystemMessage("Base"), HumanMessage("梦境中的战斗")]
    output = await model_messages(original, session, host=host)
    assert any("空间位置" in m.content for m in output)
    assert any("不可靠感知" in m.content for m in output)
    assert [m.content for m in original] == ["Base", "梦境中的战斗"]
    config = await host.call("prompt-elements", "prompt.config", {}, session)
    config["rules"] = []
    config["elements"] = [{**e, "enabled": False} for e in config["elements"]]
    await host.call("prompt-elements", "prompt.save", {"config": config}, session)
    output = await model_messages(original, session, host=host)
    assert [m.content for m in output] == ["Base", "梦境中的战斗"]
    config["rules"] = [
        {
            "id": "replace",
            "conditions": [{"source": "last_user", "pattern": "战斗"}],
            "actions": [
                {
                    "type": "replace",
                    "roles": ["user"],
                    "pattern": "战斗",
                    "replacement": "对话",
                },
                {"type": "inject", "text": "Project ${projectId}", "role": "system"},
            ],
        }
    ]
    result = await host.call(
        "prompt-elements",
        "prompt.preview",
        {
            "config": config,
            "projectId": "test",
            "messages": [{"role": "user", "content": "战斗"}],
        },
        session,
    )
    assert result["matched"] == ["replace"]
    assert any(m["content"] == "对话" for m in result["messages"])
    assert any(m["content"] == "Project test" for m in result["messages"])


@pytest.mark.parametrize(
    "name",
    ["project-statistics", "google-drive-sync", "handoff-workflow", "prompt-elements"],
)
async def test_examples_install_with_native_views_and_no_frontend_assets(
    plugin_api, client, name
):
    host, api, _ = plugin_api
    package = example_package(name)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert not any(path.startswith("frontend/") for path in archive.namelist())
    await host.install(package)
    await host.set_enabled(name, True)
    project = (
        await client.post("/api/v1/projects", data={"title": "Native example"})
    ).json()
    for view in host.get(name).manifest.views:
        assert view.renderer == "declarative" and not view.entry
        response = await api.post(
            f"/api/v1/plugins/{name}/views/{view.id}/render",
            json={"context": {"projectId": project["id"]}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["css"] and response.json()["trees"]


async def test_native_token_drafts_stay_encrypted_and_are_cleared(plugin_api, session):
    host, _, _ = plugin_api
    await host.install(example_package("google-drive-sync"))
    await host.set_enabled("google-drive-sync", True)
    params = {"viewId": "sync", "context": {}}
    secret = "native-secret-access-token"
    await host.call(
        "google-drive-sync",
        "ui.action",
        {**params, "id": "token-draft", "value": secret},
        session,
    )
    await host.call(
        "google-drive-sync", "ui.action", {**params, "id": "token"}, session
    )
    ctx = host.context("google-drive-sync", session)
    assert await ctx.secrets.get("ui.token.draft") is None
    assert (await ctx.secrets.get("oauth.tokens"))["access_token"] == secret
    document = await host.call("google-drive-sync", "ui.render", params, session)
    assert secret not in json.dumps(document)
    for path in (host.root / ".data/google-drive-sync").rglob("*.json"):
        assert secret not in path.read_text()


async def test_native_prompt_invalid_draft_does_not_break_render_or_saved_config(
    plugin_api, session
):
    host, _, _ = plugin_api
    await host.install(example_package("prompt-elements"))
    await host.set_enabled("prompt-elements", True)
    params = {"viewId": "rules", "context": {}}
    for draft in ["{broken", "null", "42"]:
        await host.call(
            "prompt-elements",
            "ui.action",
            {**params, "id": "elements", "value": draft},
            session,
        )
        assert await host.call("prompt-elements", "ui.render", params, session)
        with pytest.raises(host_tests.PluginError):
            await host.call(
                "prompt-elements", "ui.action", {**params, "id": "save"}, session
            )
    for draft in ['[{"id": 12}]', '[{"id": "x", "title": {}, "enabled": null}]']:
        await host.call(
            "prompt-elements",
            "ui.action",
            {**params, "id": "elements", "value": draft},
            session,
        )
        assert await host.call("prompt-elements", "ui.render", params, session)
    saved = await host.call("prompt-elements", "prompt.config", {}, session)
    assert len(saved["elements"]) == 3


async def test_python_sdk_call_keeps_capability_checks(plugin_api, session):
    host, api, _ = plugin_api
    await host.install(example_package("project-statistics"))
    await host.set_enabled("project-statistics", True)
    ctx = host.context("project-statistics", session)
    assert isinstance(await ctx.call("data.projects"), list)
    with pytest.raises(PermissionError, match="agent.graph"):
        await ctx.call("workflow.select", {"projectId": "missing", "provider": None})


async def test_statistics_upgrade_replaces_legacy_ui_and_keeps_settings(plugin_api):
    host, api, _ = plugin_api
    await host.install(
        host_tests.package(capabilities=["projects.read", "project.entities.read"])
    )
    await host.configure(
        "project-statistics", {"targetWords": 800, "showVolumes": False}
    )
    await host.set_enabled("project-statistics", True)
    assert (
        await api.get("/api/v1/plugins/project-statistics/assets/index.html")
    ).status_code == 200
    response = await api.put(
        "/api/v1/plugins/project-statistics/package",
        data={"trusted": "true"},
        files={
            "file": (
                "project-statistics-1.1.0.zip",
                example_package("project-statistics"),
                "application/zip",
            )
        },
    )
    assert response.status_code == 200, response.text
    plugin = host.get("project-statistics")
    assert plugin.manifest.version == "1.1.0"
    assert plugin.manifest.views[0].renderer == "declarative"
    assert plugin.enabled
    assert (
        plugin.settings["targetWords"] == 800
        and plugin.settings["showVolumes"] is False
    )
    assert not (host.root / "project-statistics/frontend").exists()
    assert (
        await api.post(
            "/api/v1/plugins/project-statistics/views/overview/render", json={}
        )
    ).status_code == 200


async def test_native_switches_do_not_mutate_global_or_other_project_defaults(
    plugin_api, client, session
):
    host, _, _ = plugin_api
    await host.install(example_package("prompt-elements"))
    await host.set_enabled("prompt-elements", True)
    first = (await client.post("/api/v1/projects", data={"title": "First"})).json()[
        "id"
    ]
    second = (await client.post("/api/v1/projects", data={"title": "Second"})).json()[
        "id"
    ]
    await host.call(
        "prompt-elements",
        "ui.action",
        {
            "viewId": "switches",
            "context": {"projectId": first},
            "id": "toggle:consistency",
            "value": False,
        },
        session,
    )
    for project_id, expected in [(first, False), (second, True), (None, True)]:
        config = await host.call(
            "prompt-elements", "prompt.config", {"projectId": project_id}, session
        )
        assert (
            next(item for item in config["elements"] if item["id"] == "consistency")[
                "enabled"
            ]
            is expected
        )
