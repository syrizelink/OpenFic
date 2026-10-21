"""A native port exercises generic overlays, package assets and post-commit usage."""

import base64
import copy
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.plugins.declarative import validate_document
from app.plugins.manifest import Manifest
from app.plugins.runtime import observe
from tests.plugins.test_examples import example_package
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")
SOURCE = Path(__file__).resolve().parents[3] / "examples/plugins/deepseek-whale"


async def install(host):
    await host.install(example_package("deepseek-whale"))
    await host.set_enabled("deepseek-whale", True)


async def test_overlay_permission_and_native_component_contract():
    manifest = json.loads((SOURCE / "plugin.json").read_text())
    assert Manifest.model_validate(manifest)
    manifest["capabilities"].remove("ui.overlay")
    with pytest.raises(ValidationError, match="ui.overlay"):
        Manifest.model_validate(manifest)
    with pytest.raises(ValueError, match="requires ui.overlay"):
        validate_document({"tree": {"type": "FloatingPanel"}}, capabilities=["ui"])
    document = validate_document(
        {
            "tree": {
                "type": "FloatingPanel",
                "props": {
                    "position": {"x": 10, "y": 20},
                    "onPositionChange": "move",
                },
                "children": {
                    "type": "Image",
                    "props": {"asset": "assets/whale.png", "alt": "Whale"},
                },
            }
        },
        capabilities=["ui", "ui.overlay"],
    )
    assert document["trees"][0]["tree"]["children"]["type"] == "Image"
    manifest["capabilities"].append("ui.overlay")
    manifest["views"][0] = {
        "id": "iframe",
        "title": "Iframe",
        "slot": "app.overlay",
        "entry": "panel/index.html",
    }
    with pytest.raises(ValidationError, match="declarative"):
        Manifest.model_validate(manifest)


async def test_assets_are_package_scoped_bounded_and_capability_checked(
    plugin_api, session
):
    host, _, _ = plugin_api
    await install(host)
    ctx = host.context("deepseek-whale", session)
    result = await ctx.assets.read("assets/whale.png")
    assert result["mime"] == "image/png"
    assert (
        base64.b64decode(result["base64"]) == (SOURCE / "assets/whale.png").read_bytes()
    )
    for path in ["../main.py", "/etc/passwd", "missing.png"]:
        with pytest.raises(ValueError):
            await ctx.assets.read(path)
    assets = host.root / "deepseek-whale/assets"
    (assets / "linked.py").symlink_to(host.root / "deepseek-whale/main.py")
    with pytest.raises(ValueError):
        await ctx.assets.read("assets/linked.py")
    (assets / "big.bin").write_bytes(b"x" * (3 * 1024 * 1024))
    with pytest.raises(ValueError, match="limit"):
        await ctx.assets.read("assets/big.bin")
    ctx.plugin.manifest.capabilities.remove("ui")
    with pytest.raises(PermissionError):
        await ctx.assets.read("assets/whale.png")
    with pytest.raises(PermissionError):
        host.context("deepseek-whale", session).invalidate_ui()


async def test_balance_accounting_stale_credit_correction_and_secret_isolation(
    plugin_api, session
):
    host, api, _ = plugin_api
    await install(host)
    await host.configure("deepseek-whale", {"apiKey": "dummy-key-a"})
    current = {"total": "100", "status": 200, "currency": "CNY"}

    def provider(request):
        assert request.url == "https://api.deepseek.com/user/balance"
        assert request.headers["Authorization"].startswith("Bearer dummy-key-")
        return httpx.Response(
            current["status"],
            json={
                "balance_infos": [
                    {
                        "currency": current["currency"],
                        "total_balance": current["total"],
                        "granted_balance": "0",
                        "topped_up_balance": current["total"],
                    }
                ]
            },
        )

    host.http_transport = httpx.MockTransport(provider)
    ctx = host.context("deepseek-whale", session)

    async def refresh():
        return await host.call("deepseek-whale", "balance.refresh", {}, session)

    assert (await refresh())["ok"]
    assert any(
        event["event"] == "ui.invalidate" and event["pluginId"] == "deepseek-whale"
        for event in host.events(0)["events"]
    )
    current["total"] = "90"
    await refresh()
    current["total"] = "110"  # Recharge does not erase previous observed spending.
    await refresh()
    current["total"] = "85"
    await refresh()
    state = await ctx.storage.get("whale.state.v1")
    row = next(iter(state["days"].values()))
    assert row["observed"] == 35 and row["credits"] == 20
    current["status"] = 503
    assert not (await refresh())["ok"]
    stale = await ctx.storage.get("whale.state.v1")
    assert stale["balance"]["total"] == 85 and stale["balance"]["stale"]
    assert next(iter(stale["days"].values()))["observed"] == 35
    action = {"viewId": "settings", "context": {}}
    await host.call(
        "deepseek-whale",
        "ui.action",
        {**action, "id": "correction-draft", "value": "17.5"},
        session,
    )
    with pytest.raises(Exception, match="未保存校正"):
        await host.call(
            "deepseek-whale", "ui.action", {**action, "id": "correct"}, session
        )
    current["status"] = 200
    await host.call("deepseek-whale", "ui.action", {**action, "id": "correct"}, session)
    current["total"] = "80"
    await refresh()
    corrected = await ctx.storage.get("whale.state.v1")
    row = next(iter(corrected["days"].values()))
    assert row["observed"] + row["correction"] == 22.5
    response = await api.get("/api/v1/plugins")
    assert "dummy-key-a" not in response.text
    logs = json.dumps(host.logs("deepseek-whale"))
    assert "dummy-key-a" not in logs
    for view in ["widget", "settings"]:
        document = await host.call(
            "deepseek-whale", "ui.render", {"viewId": view}, session
        )
        assert "dummy-key-a" not in json.dumps(document)
        validate_document(document, capabilities=ctx.plugin.manifest.capabilities)
    # Secret-only configuration changes invalidate native views too.
    cursor = host.events(0)["cursor"]
    await host.configure("deepseek-whale", {"apiKey": "dummy-key-b"})
    assert any(e["event"] == "ui.invalidate" for e in host.events(cursor)["events"])
    document = await host.call(
        "deepseek-whale", "ui.render", {"viewId": "settings"}, session
    )
    assert "账户已变更" in json.dumps(document, ensure_ascii=False)
    current["currency"] = "USD"
    await refresh()
    final = await ctx.storage.get("whale.state.v1")
    assert len(final["days"]) == 2
    assert final["balance"]["account"] != corrected["balance"]["account"]
    row = next(r for r in final["days"].values() if r["currency"] == "USD")
    assert row["observed"] == 0


async def test_usage_notifications_dedupe_preserve_currency_and_isolate_failure(
    plugin_api, session
):
    host, _, _ = plugin_api
    await install(host)
    registration = host.get("deepseek-whale").registration

    async def broken(ctx, event, next_handler):
        event["cost"] = 999  # Cannot mutate billing or another observer's payload.
        raise RuntimeError("observer failed")

    registration.hooks["usage.recorded"].insert(0, (-10, broken))
    event = {
        "event_id": "first",
        "session_id": "parent",
        "task_id": "task",
        "revision_id": "round-a",
        "currency": "USD",
        "cost": 0.01,
        "token_input": 100,
        "token_output": 20,
        "token_cache": 40,
        "model_id": "test-model",
    }
    original = copy.deepcopy(event)
    await observe("usage.recorded", event, host=host)
    await observe("usage.recorded", event, host=host)
    await observe(
        "usage.recorded",
        {
            **event,
            "event_id": "child",
            "session_id": "child",
            "parent_session_id": "parent",
            "is_subagent": True,
            "cost": 0.02,
        },
        host=host,
    )
    await observe(
        "turn.settled",
        {
            "session_id": "parent",
            "task_id": "task",
            "revision_id": "round-a",
            "status": "completed",
        },
        host=host,
    )
    ctx = host.context("deepseek-whale", session)
    state = await ctx.storage.get("whale.state.v1")
    assert event == original
    assert len(state["usage"]) == 2
    assert state["lastTurn"]["cost"] == 0.03
    assert (
        state["lastTurn"]["tokens"] == 240
    )  # Cached input is a subset, not added twice.
    assert state["lastTurn"]["currency"] == "USD" and state["days"] == {}
    # An interrupted revision remains in daily usage, but never leaks into a
    # later completed turn of the same session/task.
    for revision, cost in [("abandoned", 0.8), ("round-b", 0.04)]:
        await observe(
            "usage.recorded",
            {**event, "event_id": revision, "revision_id": revision, "cost": cost},
            host=host,
        )
    await observe(
        "turn.settled",
        {"session_id": "parent", "revision_id": "round-b", "status": "completed"},
        host=host,
    )
    assert (await ctx.storage.get("whale.state.v1"))["lastTurn"]["cost"] == 0.04
    await host.set_enabled("deepseek-whale", False)
    await observe("usage.recorded", {**event, "event_id": "disabled"}, host=host)
    assert len((await ctx.storage.get("whale.state.v1"))["usage"]) == 4
