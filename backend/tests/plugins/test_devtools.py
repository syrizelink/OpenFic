"""Real checker, development replacement and opt-in diagnostic contracts."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from app.plugins.checker import check_plugin
from app.plugins.development import DevelopmentSession
from app.plugins.packages import build_package
from app.plugins.runtime import observe
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")
SOURCE = Path(__file__).resolve().parents[3] / "examples/plugins/devtools-demo"


def copy_source(tmp_path):
    target = tmp_path / "source"
    shutil.copytree(
        SOURCE,
        target,
        ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".openfic-dev"),
    )
    return target


async def test_offline_checker_reports_real_ui_errors_without_importing_code(tmp_path):
    root = copy_source(tmp_path)
    marker = tmp_path / "must-not-exist"
    path = root / "backend/main.py"
    original = path.read_text()
    path.write_text(
        original
        + f'\nfrom pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n'
    )
    valid = check_plugin(root)
    assert valid["ok"] and valid["coverage"]["staticNodes"] > 5
    assert not marker.exists()
    assert any(check["status"] == "not-run" for check in valid["checks"])
    path.write_text(
        original
        + '\ndef invalid():\n return {"type":"Button","props":{"asset":"x","size":"99"}}\n'
    )
    invalid = check_plugin(root)
    codes = {item["code"] for item in invalid["diagnostics"]}
    assert not invalid["ok"] and {"ui.prop", "ui.value"} <= codes
    path.write_text(
        original
        + '\ndef missing():\n return {"type":"Image","props":{"asset":"../backend/main.py"}}\n'
    )
    assert "ui.asset" in {item["code"] for item in check_plugin(root)["diagnostics"]}
    # JSON Schema dictionaries are not component trees.
    path.write_text(
        original
        + '\nSCHEMA = {"type":"object","properties":{"title":{"type":"string"}}}\n'
    )
    assert check_plugin(root)["ok"]


async def test_checker_uses_host_css_compiler_and_package_validation(tmp_path):
    root = copy_source(tmp_path)
    baseline = build_package(root)
    for ignored in ("node_modules", ".openfic-dev"):
        directory = root / ignored
        directory.mkdir()
        (directory / "private.py").write_text(
            "not valid Python and not package content"
        )
        (directory / "outside").symlink_to(tmp_path, target_is_directory=True)
    assert build_package(root) == baseline
    document = root / "ui/overview.json"
    value = json.loads(document.read_text())
    value["css"] = '@import url("https://example.com/filtered.css"); .ok { color:red; }'
    document.write_text(json.dumps(value))
    report = check_plugin(root)
    assert report["ok"] and any(
        d["code"] == "css.filtered" for d in report["diagnostics"]
    )
    value["tree"] = {"type": "FloatingPanel", "props": {}}
    manifest = json.loads((root / "plugin.json").read_text())
    manifest["views"] = [manifest["views"][0]]
    manifest["capabilities"].remove("ui.overlay")
    (root / "plugin.json").write_text(json.dumps(manifest))
    document.write_text(json.dumps(value))
    assert not check_plugin(root)["ok"]
    (root / "frontend/link").symlink_to(root / "backend/main.py")
    report = check_plugin(root)
    assert not report["ok"] and report["diagnostics"][0]["code"] == "package.invalid"


async def test_inspector_is_off_by_default_and_redacts_both_trace_origins(
    plugin_api, session
):
    host, client, _ = plugin_api
    await host.install(build_package(SOURCE))
    await host.set_enabled("devtools-demo", True)
    assert (await client.get("/api/v1/plugins/development")).json() == {
        "enabled": False,
        "inspector": False,
    }
    assert (
        await client.get("/api/v1/plugins/devtools-demo/inspector")
    ).status_code == 404
    await host.call("devtools-demo", "ui.render", {"viewId": "overview"}, session)
    assert host.diagnostics.snapshot()["entries"] == []
    host.diagnostics.enabled = True
    key = "private-sdk-diagnostic-key"
    await host.configure("devtools-demo", {"apiKey": key})
    await host.call(
        "devtools-demo", "ui.action", {"viewId": "overview", "id": "secret"}, session
    )
    payload = {
        "pluginId": "devtools-demo",
        "viewId": "overview",
        "kind": "render",
        "method": "ui.render",
        "status": "ok",
        "request": {"authorization": "Bearer hidden"},
        "result": {"plain": key},
    }
    response = await client.post(
        "/api/v1/plugins/devtools-demo/inspector/report", json=payload
    )
    assert response.status_code == 204
    entries = (await client.get("/api/v1/plugins/devtools-demo/inspector")).json()[
        "entries"
    ]
    assert (
        entries
        and key not in json.dumps(entries)
        and "Bearer hidden" not in json.dumps(entries)
    )
    assert any(
        e["kind"] == "frontend.render" and e["viewId"] == "overview" for e in entries
    )
    assert any(
        e["method"] == "secrets.set" and e["request"] == "[redacted]" for e in entries
    )
    # A rejected secret write must hide its value too, before it can be remembered.
    with pytest.raises(Exception):
        await host.call(
            "devtools-demo",
            "sdk.secrets.set",
            {"key": "", "value": "rejected-private-value"},
            session,
        )
    assert "rejected-private-value" not in json.dumps(host.diagnostics.snapshot())
    await host.call(
        "devtools-demo", "sdk.secrets.set", {"key": "short", "value": "xyz"}, session
    )
    await client.post(
        "/api/v1/plugins/devtools-demo/inspector/report",
        json={**payload, "result": {"plain": "xyz"}},
    )
    assert "xyz" not in json.dumps(host.diagnostics.snapshot())
    for index in range(210):
        host.diagnostics.add(host.get("devtools-demo"), "test", str(index))
    assert len(host.diagnostics.snapshot()["entries"]) == 200
    assert (
        await client.post(
            "/api/v1/plugins/devtools-demo/inspector/report",
            json={**payload, "pluginId": "another-plugin"},
        )
    ).status_code == 422
    assert (
        await client.delete("/api/v1/plugins/devtools-demo/inspector")
    ).status_code == 200
    assert host.diagnostics.snapshot()["entries"] == []


async def test_real_permissions_and_observers_are_visible_without_changing_behavior(
    plugin_api, session
):
    host, _, _ = plugin_api
    host.diagnostics.enabled = True
    await host.install(build_package(SOURCE))
    await host.set_enabled("devtools-demo", True)
    with pytest.raises(Exception, match="projects.read"):
        await host.call(
            "devtools-demo",
            "ui.action",
            {"viewId": "overview", "id": "permission"},
            session,
        )
    assert any(
        e["status"] == "error" and e["method"] == "api.request"
        for e in host.diagnostics.snapshot()["entries"]
    )
    seen = []

    async def observer(ctx, payload, next_handler):
        seen.append(payload)
        return await next_handler(payload)

    host.get("devtools-demo").registration.hooks["usage.recorded"] = [(0, observer)]
    await observe("usage.recorded", {"cost": 0.5}, host=host)
    assert seen == [{"cost": 0.5}]
    assert any(e["kind"] == "observer" for e in host.diagnostics.snapshot()["entries"])


async def test_hot_reload_preserves_data_and_rolls_back_invalid_activation(
    plugin_api, session, tmp_path
):
    host, _, _ = plugin_api
    source = copy_source(tmp_path)
    development = DevelopmentSession(host, source)
    await development.start()
    try:
        assert development.status == "ready" and development.revision == 1
        await host.call(
            "devtools-demo",
            "ui.action",
            {"viewId": "overview", "id": "increment"},
            session,
        )
        path = source / "backend/main.py"
        original = path.read_text()
        path.write_text(original + '\nraise RuntimeError("broken activation")\n')
        await development.reload()
        assert development.status == "error" and development.revision == 1
        document = await host.call(
            "devtools-demo", "ui.render", {"viewId": "overview"}, session
        )
        assert "计数：1" in json.dumps(document, ensure_ascii=False)
        path.write_text(original.replace("原生 SDK 开发示例", "热重载后的原生组件"))
        await development.reload()
        assert development.status == "ready" and development.revision == 2
        document = await host.call(
            "devtools-demo", "ui.render", {"viewId": "overview"}, session
        )
        assert "热重载后的原生组件" in json.dumps(document, ensure_ascii=False)
        assert "计数：1" in json.dumps(document, ensure_ascii=False)
        (source / "frontend/app.js").write_text(
            (source / "frontend/app.js").read_text() + "\n// watched asset edit\n"
        )

        async def changed():
            while development.revision == 2:
                await asyncio.sleep(0.1)

        await asyncio.wait_for(changed(), timeout=10)
        assert development.revision == 3
    finally:
        await development.close()
    # Same-version replacement remains forbidden outside the explicit dev session.
    with pytest.raises(Exception, match="newer"):
        await host.install(build_package(source), update_id="devtools-demo")


async def test_cli_is_offline_strict_and_pack_gated(tmp_path):
    import os
    import subprocess
    import sys

    root = copy_source(tmp_path)
    target_data = tmp_path / "no-application-data"
    env = {**os.environ, "OPENFIC_DATA_DIR": str(target_data)}
    command = [sys.executable, "-m", "app.cli", "plugin"]
    result = subprocess.run(
        [*command, "check", str(root), "--json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0 and json.loads(result.stdout)["ok"]
    assert not target_data.exists(), (
        "Offline checks must not import settings or create encryption/database files"
    )
    strict = subprocess.run(
        [*command, "check", str(root), "--json", "--strict"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert strict.returncode == 1 and not json.loads(strict.stdout)["ok"]
    output = tmp_path / "demo.zip"
    packed = subprocess.run(
        [*command, "pack", str(root), "--output", str(output), "--json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert packed.returncode == 0 and output.is_file()
    assert check_plugin(output)["ok"]
    (root / "frontend/app.js").unlink()
    report = check_plugin(root)
    assert not report["ok"] and any(
        item["code"] == "frontend.asset" for item in report["diagnostics"]
    )
