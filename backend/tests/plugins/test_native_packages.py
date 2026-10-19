"""Only native packages execute; older native exports remain installable."""

import io
import json
import zipfile

import pytest

from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api
pytestmark = pytest.mark.asyncio(loop_scope="module")


def legacy_manifest():
    return {
        "id": "legacy-mod",
        "name": "Previously converted Mod",
        "version": "1.0.0",
        "api_version": 1,
        "format": "claude-mod",
        "compatibility": {"modules": ["hooks/register.mjs"], "adapterVersion": 3},
    }


@pytest.mark.parametrize("kind", ["raw", "wrapped", "converted"])
async def test_unsupported_packages_rejected_without_affecting_native_plugins(
    plugin_api, kind
):
    host, api, _ = plugin_api
    await host.install(host_tests.package())
    await host.set_enabled("project-statistics", True)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        if kind == "converted":
            archive.writestr("plugin.json", json.dumps(legacy_manifest()))
        else:
            prefix = "repository/" if kind == "wrapped" else ""
            archive.writestr(
                prefix + ".claude-plugin/plugin.json",
                json.dumps({"name": "legacy-mod", "version": "1.0.0"}),
            )
            archive.writestr(
                prefix + "hooks/hooks.json",
                json.dumps({"modules": ["./register.mjs"]}),
            )
            archive.writestr("hooks/register.mjs", "export function register() {}")
    response = await host_tests.install(api, output.getvalue())
    assert response.status_code == 400
    assert ("format" if kind == "converted" else "plugin.json") in response.text
    assert list(host.plugins) == ["project-statistics"]
    assert host.get("project-statistics").registration is not None
    assert not list(host.root.glob(".install-*"))
    assert not (host.root / "legacy-mod").exists()


async def test_startup_skips_old_mod_without_execution_or_data_deletion(plugin_api):
    host, _, _ = plugin_api
    await host.install(host_tests.package())
    await host.set_enabled("project-statistics", True)
    await host.close()
    directory = host.root / "legacy-mod"
    directory.mkdir()
    marker = directory / "executed"
    manifest = {**legacy_manifest(), "backend": "main.py"}
    (directory / "plugin.json").write_text(json.dumps(manifest))
    (directory / "main.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
        "def register(host): pass\n"
    )
    data = host.root / ".data/legacy-mod"
    data.mkdir(parents=True)
    (data / "state.json").write_text('{"preserved": true}')
    registry_path = host.root / ".registry.json"
    registry = json.loads(registry_path.read_text())
    registry["legacy-mod"] = {"enabled": True}
    registry_path.write_text(json.dumps(registry))
    await host.start()
    assert list(host.plugins) == ["project-statistics"]
    assert host.get("project-statistics").registration is not None
    assert not marker.exists()
    assert json.loads((data / "state.json").read_text()) == {"preserved": True}
    assert json.loads((directory / "plugin.json").read_text()) == manifest


async def test_older_native_export_metadata_is_accepted_but_not_emitted(plugin_api):
    host, _, _ = plugin_api
    original = host_tests.package()
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(
        output, "w"
    ) as target:
        for entry in source.namelist():
            content = source.read(entry)
            if entry == "plugin.json":
                manifest = json.loads(content)
                manifest.update(format="openfic", compatibility={})
                content = json.dumps(manifest).encode()
            target.writestr(entry, content)
    result = await host.install(output.getvalue())
    assert "compatibility" not in result
    await host.set_enabled("project-statistics", True)
    await host.close()
    await host.start()
    assert host.get("project-statistics").registration is not None
    assert "compatibility" not in host.describe(host.get("project-statistics"))
