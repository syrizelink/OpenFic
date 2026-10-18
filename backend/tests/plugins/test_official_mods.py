"""Real, unmodified Anthropic Mods pinned by commit and source hashes."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from app.plugins.runtime import dispatch
from tests.plugins import test_host as host_tests
from tests.plugins.test_sdk import mod_bundle

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")
FIXTURES = Path(__file__).parent / "fixtures/claude-playground"


def official_package(name):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((FIXTURES / name).rglob("*")):
            if path.is_file():
                archive.writestr(
                    path.relative_to(FIXTURES / name).as_posix(), path.read_bytes()
                )
    return buffer.getvalue()


def rendered(result):
    return json.dumps(result["trees"], ensure_ascii=False)


def action_id(result, label):
    def visit(value):
        if isinstance(value, dict):
            if value.get("props", {}).get("label") == label:
                return value["props"]["onPress"]
            for child in value.values():
                if found := visit(child):
                    return found
        elif isinstance(value, list):
            for child in value:
                if found := visit(child):
                    return found

    return visit(result["trees"])


@pytest.mark.parametrize("name", ["token-weather", "replay-theater", "blast-radius"])
async def test_official_packages_are_unmodified_and_installable(
    plugin_api, session, name
):
    host, _, _ = plugin_api
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    for path, checksum in provenance["files"].items():
        assert hashlib.sha256((FIXTURES / path).read_bytes()).hexdigest() == checksum
    await host.install(official_package(name))
    await host.set_enabled(name, True)
    description = host.describe(host.get(name))
    assert description["status"] == "enabled"
    assert description["format"] == "claude-mod"
    if name == "blast-radius":
        assert any(
            "$.process" in warning
            for warning in description["compatibility"]["warnings"]
        )
        assert any(
            "Bash" in warning for warning in description["compatibility"]["warnings"]
        )
    else:
        assert not description["compatibility"]["warnings"]
        assert any(
            view["slot"] == "assistant.above-prompt" for view in description["views"]
        )
    result = await host.call(name, "mod.inspect", {}, session)
    assert all(tree["tree"] is None for tree in result["trees"])


async def test_official_token_weather_reads_real_task_usage(
    plugin_api, session, client
):
    from app.storage.models.task import Task

    host, _, _ = plugin_api
    project = (await client.post("/api/v1/projects", data={"title": "Weather"})).json()
    task = Task(
        project_id=project["id"],
        title="Weather",
        mode="agent",
        agent_session_id="weather-session",
    )
    session.add(task)
    await session.commit()
    runtime = {
        "project_id": project["id"],
        "task_id": task.id,
        "session_id": "weather-session",
        "model_config": {"max_context_tokens": 32000},
    }
    await host.install(official_package("token-weather"))
    await host.set_enabled("token-weather", True)
    event = {"projectId": project["id"], "sessionId": "weather-session"}
    await dispatch("session.start", event, session, host=host, runtime=runtime)
    assert "Clear" in rendered(
        await host.call("token-weather", "mod.inspect", {}, session)
    )
    task.context_input_tokens = 10000
    await session.commit()
    await dispatch("turn.complete", event, session, host=host, runtime=runtime)
    result = await host.call(
        "token-weather", "mod.inspect", {"slot": "assistant.above-prompt"}, session
    )
    assert "Cloudy" in rendered(result)
    assert "31% of context" in rendered(result)
    assert "10k / 32k" in rendered(result)
    assert len(result["trees"]) == 1
    task.context_input_tokens = 30000
    await session.commit()
    await dispatch("turn.complete", event, session, host=host, runtime=runtime)
    result = await host.call("token-weather", "mod.inspect", {}, session)
    assert "Compact soon" in rendered(result)
    assert "▲ +20k last turn" in rendered(result)


async def test_official_replay_records_native_chapter_tools_and_pane_controls(
    plugin_api, session
):
    from app.agent_runtime.tools.impls.chapter.refs import VolumeRef, ChapterRef

    host, _, _ = plugin_api
    await host.install(official_package("replay-theater"))
    await host.set_enabled("replay-theater", True)
    state = {"project_id": "project", "session_id": "session"}
    await dispatch("turn.start", {}, session, host=host, runtime=state)
    seen = []

    async def execute(event):
        seen.append(event)
        return {"result": '{"success":true}'}

    for tool, arguments in [
        (
            "write_chapter",
            {
                "title": "New chapter",
                "content": "Created chapter body",
                "volume_ref": VolumeRef(type="title", value="volume"),
            },
        ),
        (
            "edit_chapter",
            {
                "chapter_ref": ChapterRef(type="title", value="chapter"),
                "old_content": "Before",
                "new_content": "After",
                "volume_ref": VolumeRef(type="title", value="volume"),
            },
        ),
    ]:
        await dispatch(
            "tool.call",
            {"tool": tool, "input": arguments},
            session,
            host=host,
            runtime=state,
            terminal=execute,
        )
        assert seen[-1]["tool"] == tool
        assert seen[-1]["input"] == arguments
    await dispatch("turn.complete", {}, session, host=host, runtime=state)
    assert "Replay: 2 edits" in rendered(
        await host.call("replay-theater", "mod.inspect", {}, session)
    )
    await host.call("replay-theater", "mod.command", {"command": "replay"}, session)
    first = await host.call("replay-theater", "mod.inspect", {}, session)
    assert first["panes"][0]["id"] == "replay-theater"
    assert "step 1 of 2" in rendered(first)
    assert "Created chapter body" in rendered(first)
    await host.call(
        "replay-theater", "mod.action", {"id": action_id(first, "Next ▶")}, session
    )
    second = await host.call("replay-theater", "mod.inspect", {}, session)
    assert "step 2 of 2" in rendered(second)
    assert "- Before" in rendered(second) and "+ After" in rendered(second)
    await host.call(
        "replay-theater", "mod.action", {"id": action_id(second, "◀ Prev")}, session
    )
    previous = await host.call("replay-theater", "mod.inspect", {}, session)
    assert "step 1 of 2" in rendered(previous)
    await host.call(
        "replay-theater", "mod.action", {"id": action_id(previous, "Close")}, session
    )
    assert not (await host.call("replay-theater", "mod.inspect", {}, session))["panes"]
    await host.call("replay-theater", "mod.command", {"command": "replay"}, session)
    await host.call("replay-theater", "mod.close", {"id": "replay-theater"}, session)
    closed = await host.call("replay-theater", "mod.inspect", {}, session)
    assert not closed["panes"] and "Replay: 2 edits" in rendered(closed)
    for _ in range(2):
        await dispatch("session.start", {}, session, host=host)
    assert (
        len((await host.call("replay-theater", "mod.inspect", {}, session))["commands"])
        == 1
    )


async def test_mod_edit_translation_preserves_native_execution_and_rewrites(
    plugin_api, session
):
    host, _, _ = plugin_api
    await host.install(
        mod_bundle(
            "export function register(on){on('tool.call',{tool:'Edit'},async($,e,next)=>next({...e,new_string:e.new_string+' translated'}))}"
        )
    )
    await host.set_enabled("demo-mod", True)
    observed = []

    async def execute(event):
        observed.append(event)
        return {"result": "executed"}

    original = {
        "tool": "edit_chapter",
        "input": {
            "chapter_ref": {"type": "id", "value": "chapter"},
            "old_content": "old",
            "new_content": "new",
        },
    }
    result = await dispatch("tool.call", original, session, host=host, terminal=execute)
    assert result == {"result": "executed"}
    assert observed[0]["tool"] == "edit_chapter"
    assert observed[0]["input"]["new_content"] == "new translated"
    assert observed[0]["input"]["chapter_ref"] == original["input"]["chapter_ref"]


async def test_official_blast_radius_warns_and_refuses_without_process_execution(
    plugin_api, session
):
    host, _, _ = plugin_api
    await host.install(official_package("blast-radius"))
    await host.set_enabled("blast-radius", True)
    observed = []

    async def execute(event):
        observed.append(event)
        return {"result": "allowed"}

    # No shell is executed: this is an event/continuation contract check.
    result = await dispatch(
        "tool.call",
        {"tool": "Bash", "input": {"command": "rm -rf build"}},
        session,
        host=host,
        terminal=execute,
    )
    assert result.get("deny")
    assert not observed
    assert not (await host.call("blast-radius", "mod.inspect", {}, session))["panes"]
    result = await dispatch(
        "tool.call",
        {"tool": "Bash", "input": {"command": "printf hello"}},
        session,
        host=host,
        terminal=execute,
    )
    assert result == {"result": "allowed"}
    assert len(observed) == 1


@pytest.mark.parametrize("change", ["tool:'Write'", "file_path:'/etc/passwd'"])
async def test_mod_document_translation_cannot_redirect_execution(
    plugin_api, session, change
):
    host, _, _ = plugin_api
    await host.install(
        mod_bundle(
            "export function register(on){on('tool.call',{tool:'Edit'},($,e,next)=>next({...e,"
            + change
            + "}))}"
        )
    )
    await host.set_enabled("demo-mod", True)
    called = []

    async def execute(event):
        called.append(event)
        return {"result": "must not execute"}

    with pytest.raises(ValueError, match="cannot change|cannot redirect"):
        await dispatch(
            "tool.call",
            {
                "tool": "edit_chapter",
                "input": {
                    "old_content": "old",
                    "new_content": "new",
                    "chapter_ref": {"type": "title", "value": "chapter"},
                },
            },
            session,
            host=host,
            terminal=execute,
        )
    assert not called


async def test_official_mod_preserves_langgraph_interrupts(plugin_api, session):
    from langgraph.errors import GraphInterrupt

    host, _, _ = plugin_api
    await host.install(official_package("replay-theater"))
    await host.set_enabled("replay-theater", True)
    interruption = GraphInterrupt(())

    async def pause(event):
        raise interruption

    with pytest.raises(GraphInterrupt) as raised:
        await dispatch(
            "tool.call",
            {"tool": "ask_user", "input": {}},
            session,
            host=host,
            terminal=pause,
        )
    assert raised.value is interruption
    assert all(
        tree["tree"] is None
        for tree in (await host.call("replay-theater", "mod.inspect", {}, session))[
            "trees"
        ]
    )
