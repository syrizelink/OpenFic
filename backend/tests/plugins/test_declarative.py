"""Declarative protocol validation and authenticated, bound view transport."""

import io
import json
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.plugins.declarative import validate_document
from app.plugins.manifest import Manifest, View
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api

pytestmark = pytest.mark.asyncio(loop_scope="module")
FIXTURE = (
    Path(__file__).resolve().parents[3] / "frontend/e2e/fixtures/plugin-declarative"
)


def bundle():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in FIXTURE.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.writestr(
                    path.relative_to(FIXTURE).as_posix(), path.read_bytes()
                )
    return buffer.getvalue()


async def test_mixed_views_and_bound_actions(plugin_api):
    from app.api.routers.plugins import plugin_exception_handler
    from app.plugins.host import PluginError

    host, api, app = plugin_api
    app.add_exception_handler(PluginError, plugin_exception_handler)
    response = await host_tests.install(api, bundle())
    assert response.status_code == 201, response.text
    await host.set_enabled("declarative-test", True)
    base = "/api/v1/plugins/declarative-test/views"
    assert (await api.post(base + "/native")).status_code == 409
    assert (await api.post(base + "/legacy")).status_code == 200
    assert (await api.post(base + "/legacy/render", json={})).status_code == 404
    result = await api.post(
        base + "/native/render", json={"context": {"projectId": "project"}}
    )
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 1
    assert "Count: 0" in result.text
    assert "<img src=x onerror=alert(1)>" in result.text
    native = host.get("declarative-test")
    native.registration.commands["ui.render"] = lambda context, params: {
        "tree": {"type": "Text", "props": {"style": "bad"}}
    }
    assert (await api.post(base + "/native/render", json={})).status_code == 422
    # Restore registration through the ordinary lifecycle.
    await host.set_enabled("declarative-test", False)
    await host.set_enabled("declarative-test", True)
    result = await api.post(
        base + "/native/action",
        json={"id": "increment", "event": "press", "method": "sdk.storage.delete"},
    )
    assert result.status_code == 422  # Cannot select a different RPC command.
    assert (
        await api.post(base + "/native/action", json={"id": "increment"})
    ).status_code == 200
    assert "Count: 1" in (await api.post(base + "/native/render", json={})).text
    assert (
        await api.post(
            base + "/native/action", json={"id": "name", "value": "a" * 65000}
        )
    ).status_code == 422
    await host.set_enabled("declarative-test", False)
    assert (await api.post(base + "/native/render", json={})).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"renderer": "unknown"},
        {"renderer": "declarative"},
        {"renderer": "declarative", "render": "sdk.storage.get", "action": "ui.action"},
        {"renderer": "iframe", "entry": "frontend/page.html", "action": "ui.action"},
    ],
)
async def test_invalid_view_contract(changes):
    with pytest.raises(ValidationError):
        View(id="test", title="Test", **changes)


async def test_explicit_ui_capability_and_legacy_default():
    assert (
        View(id="test", title="Test", entry="frontend/page.html").renderer == "iframe"
    )
    manifest = json.loads((FIXTURE / "plugin.json").read_text())
    manifest["capabilities"] = []
    with pytest.raises(ValidationError, match="ui capability"):
        Manifest.model_validate(manifest)


@pytest.mark.parametrize(
    "tree",
    [
        {"type": "script", "children": "alert(1)"},
        {"type": "Text", "props": {"dangerouslySetInnerHTML": "bad"}},
        {"type": "Box", "props": {"style": {"position": "fixed"}}},
        {"type": "Button", "props": {"onPress": {"code": "alert(1)"}}},
        {"type": "Select", "props": {"options": "invalid"}},
    ],
)
async def test_reject_executable_and_unbounded_ui(tree):
    with pytest.raises(ValueError):
        validate_document({"tree": tree})


async def test_tree_budgets_and_safe_normalization():
    tree = "leaf"
    for _ in range(34):
        tree = {"type": "Box", "children": tree}
    with pytest.raises(ValueError, match="depth/node"):
        validate_document({"tree": tree})
    with pytest.raises(ValueError, match="depth/node"):
        validate_document({"tree": ["x"] * 4097})
    with pytest.raises(ValueError, match="1 MiB"):
        validate_document({"tree": "x" * 1048577})
    result = validate_document(
        {"tree": {"type": "Text", "props": {"children": "<script>"}}}
    )
    assert result["trees"][0]["tree"] == {
        "type": "Text",
        "props": {},
        "children": "<script>",
    }


@pytest.mark.parametrize(
    "document",
    [
        {"panes": ["bad"]},
        {"commands": [None]},
        {"trees": [{"component": "script"}]},
        {"tree": {"type": "Button", "props": {"disabled": "false"}}},
        {"tree": {"type": "Box", "props": {"gap": "100"}}},
        {"tree": {"type": "Button", "props": {"onPress": True}}},
    ],
)
async def test_invalid_metadata_and_property_types(document):
    with pytest.raises(ValueError):
        validate_document(document)


async def test_unregistered_render_command_is_reported(plugin_api):
    from app.plugins.host import PluginError

    host, _, _ = plugin_api
    await host.install(bundle())
    host.get("declarative-test").manifest.views[0].render = "missing.render"
    with pytest.raises(PluginError, match="unregistered command"):
        await host.set_enabled("declarative-test", True)
