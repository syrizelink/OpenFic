"""Declarative protocol validation and authenticated, bound view transport."""

import io
import base64
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.plugins.declarative import validate_document
from app.plugins.manifest import Manifest, View
from tests.plugins import test_host as host_tests

plugin_api = host_tests.plugin_api

pytestmark = pytest.mark.asyncio(loop_scope="module")
FIXTURE = Path(__file__).with_name("fixtures") / "plugin-declarative"


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


async def test_statusbar_content_tracks_state_and_rejects_custom_ui(plugin_api):
    from app.api.routers.plugins import plugin_exception_handler
    from app.plugins.host import PluginError

    host, api, app = plugin_api
    app.add_exception_handler(PluginError, plugin_exception_handler)
    assert (await host_tests.install(api, bundle())).status_code == 201
    await host.set_enabled("declarative-test", True)
    base = "/api/v1/plugins/declarative-test/views"
    response = await api.post(base + "/status/status", json={})
    assert response.status_code == 200
    assert response.json()["items"] == [{"type": "icon", "name": "Activity"}, {"type": "text", "text": "0"}]
    assert (await api.post(base + "/native/action", json={"id": "increment"})).status_code == 200
    assert (await api.post(base + "/status/status", json={})).json()["items"][1]["text"] == "1"
    registration = host.get("declarative-test").registration
    registration.commands["ui.status"] = lambda context, params: {"items": [{"type": "text", "text": "x", "style": "bad"}]}
    assert (await api.post(base + "/status/status", json={})).status_code == 422
    registration.commands["ui.status"] = lambda context, params: {"items": [{"type": "asset", "path": "../secret"}]}
    assert (await api.post(base + "/status/status", json={})).status_code == 422
    registration.commands["ui.status"] = lambda context, params: {"items": [{"type": "asset", "path": "main.py"}]}
    assert (await api.post(base + "/status/status", json={})).status_code == 422
    registration.commands["ui.status"] = lambda context, params: {"items": [{"type": "text", "text": "x" * 10000}, {"type": "icon", "name": "CloudUpload"}, {"type": "text", "text": "end"}]}
    response = await api.post(base + "/status/status", json={})
    assert len(response.json()["items"][0]["text"]) == 10000
    assert [item["type"] for item in response.json()["items"]] == ["text", "icon", "text"]
    assert (await api.get("/api/v1/plugins/declarative-test/status-icon", params={"path": "main.py"})).status_code == 404
    icon = host.root / "declarative-test" / "panel" / "icon.png"
    icon.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
    response = await api.get("/api/v1/plugins/declarative-test/status-icon", params={"path": "panel/icon.png"})
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    await host.set_enabled("declarative-test", False)
    assert (await api.post(base + "/status/status", json={})).status_code == 409


async def test_invalidate_ui_scopes_notifications_to_plugin_views(plugin_api, session, monkeypatch):
    host, api, _ = plugin_api
    assert (await host_tests.install(api, bundle())).status_code == 201
    await host.set_enabled("declarative-test", True)
    emit = Mock()
    monkeypatch.setattr(host, "emit", emit)
    context = host.context("declarative-test", session)

    context.invalidate_ui("status")
    emit.assert_called_once_with("ui.invalidate", {"viewId": "status"}, "declarative-test")
    emit.reset_mock()
    await context.call("ui.invalidate", {"viewId": "native"})
    emit.assert_called_once_with("ui.invalidate", {"viewId": "native"}, "declarative-test")
    emit.reset_mock()
    context.invalidate_ui()
    emit.assert_called_once_with("ui.invalidate", {}, "declarative-test")
    emit.reset_mock()
    with pytest.raises(ValueError, match="Unknown plugin view"):
        context.invalidate_ui("another-plugin-view")
    emit.assert_not_called()


@pytest.mark.parametrize("presentation", ["none", "popover", "dialog"])
async def test_statusbar_view_contract(presentation):
    fields = {"id": "status", "title": "Status", "slot": "statusbar", "status": "ui.status", "presentation": presentation}
    if presentation != "none":
        fields["entry"] = "panel/index.html"
    assert View.model_validate(fields).presentation == presentation
    with pytest.raises(ValidationError):
        View.model_validate({**fields, "status": "sdk.storage.get"})
    with pytest.raises(ValidationError):
        View.model_validate({**fields, "slot": "settings.plugins"})


@pytest.mark.parametrize(
    "changes",
    [
        {"renderer": "unknown"},
        {"renderer": "declarative"},
        {"renderer": "declarative", "render": "sdk.storage.get", "action": "ui.action"},
        {"renderer": "iframe", "entry": "panel/page.html", "action": "ui.action"},
    ],
)
async def test_invalid_view_contract(changes):
    with pytest.raises(ValidationError):
        View(id="test", title="Test", **changes)


async def test_explicit_ui_capability_and_legacy_default():
    assert (
        View(id="test", title="Test", entry="panel/page.html").renderer == "iframe"
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
        {"type": "Box", "props": {"style": {"position": {"invalid": True}}}},
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


async def test_registry_priority_namespaces_and_live_catalogue(plugin_api):
    from app.plugins.declarative import CATALOGUE, resolve_component

    assert len(CATALOGUE["radix"]) >= 120
    assert resolve_component("Spinner")[:2] == ("project", "Spinner")
    assert resolve_component("Radix.Spinner")[:2] == ("radix", "Spinner")
    assert resolve_component("Select")[:2] == ("project", "LabeledSelect")
    assert resolve_component("ModelSelector")[:2] == ("project", "ModelIdSelect")
    host, api, _ = plugin_api
    response = await api.get("/api/v1/plugins/catalogue")
    assert response.status_code == 200
    assert response.json()["ui"] == CATALOGUE
    await host.install(bundle())
    await host.set_enabled("declarative-test", True)
    response = await api.post(
        "/api/v1/plugins/declarative-test/rpc",
        json={"method": "sdk.catalogue", "params": {}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["ui"] == CATALOGUE


async def test_responsive_props_css_style_and_array_events(plugin_api):
    document = {
        "css": ".panel { color: rebeccapurple }",
        "tree": {
            "type": "Grid",
            "props": {
                "columns": {"initial": "1", "md": "2"},
                "gap": "3",
                "style": {"--panel-color": "#123", "border-radius": 12},
                "aria-label": "Grid",
                "data-testid": "grid",
            },
            "children": [
                {
                    "type": "Radix.Button",
                    "props": {
                        "size": {"initial": "1", "md": "3"},
                        "variant": "outline",
                        "color": "violet",
                        "highContrast": True,
                    },
                },
                {
                    "type": "Slider",
                    "props": {
                        "value": [10, 20],
                        "min": 0,
                        "max": 200,
                        "onValueCommit": "range",
                    },
                },
                {
                    "type": "TextArea",
                    "props": {"rows": 4, "resize": "vertical", "onChange": "text"},
                },
            ],
        },
    }
    result = validate_document(document, capabilities=[])
    assert result["css"] == document["css"]
    assert result["trees"][0]["tree"]["props"] == document["tree"]["props"]
    host, api, _ = plugin_api
    await host.install(bundle())
    await host.set_enabled("declarative-test", True)
    seen = []
    host.get("declarative-test").registration.commands["ui.action"] = (
        lambda ctx, params: seen.append(params["value"])
    )
    response = await api.post(
        "/api/v1/plugins/declarative-test/views/native/action",
        json={"id": "range", "value": [10, 20]},
    )
    assert response.status_code == 200, response.text
    assert seen == [[10, 20]]


@pytest.mark.parametrize(
    "name,capability",
    [
        ("ModelSelector", "models.read"),
        ("ProjectSelector", "projects.read"),
        ("ProjectGridSelector", "projects.read"),
    ],
)
async def test_data_components_require_capability(name, capability):
    document = {"tree": {"type": name}}
    with pytest.raises(ValueError, match=capability):
        validate_document(document, capabilities=["ui"])
    assert validate_document(document, capabilities=["ui", capability])


@pytest.mark.parametrize(
    "document",
    [
        {"css": "x" * 65537},
        {"css": {"body": "red"}},
        {"tree": {"type": "Button", "props": {"size": {"tablet": "2"}}}},
        {"tree": {"type": "Button", "props": {"size": "9"}}},
        {"tree": {"type": "Slider", "props": {"value": [True]}}},
        {"tree": {"type": "CheckboxGroup.Root", "props": {"value": [123]}}},
        {"tree": {"type": "Text", "props": {"style": {"behavior": "url(x)"}}}},
        {"tree": {"type": "Text", "props": {"aria-label": {"nested": True}}}},
        {"tree": {"type": "Dialog.Content"}},
        {"tree": {"type": "Button", "props": {"asChild": True}, "children": "text"}},
    ],
)
async def test_reject_invalid_expanded_protocol(document):
    with pytest.raises(ValueError):
        validate_document(document)


async def test_compound_components_and_as_child():
    document = {
        "tree": {
            "type": "Dialog.Root",
            "children": [
                {
                    "type": "Dialog.Trigger",
                    "props": {"asChild": True},
                    "children": {"type": "Button", "children": "Open"},
                },
                {
                    "type": "Dialog.Content",
                    "children": {"type": "Dialog.Title", "children": "Title"},
                },
            ],
        }
    }
    assert validate_document(document)
    assert (
        Path(__file__).resolve().parents[3] / "packages/plugin-sdk/index.d.ts"
    ).read_bytes() == (
        Path(__file__).resolve().parents[2] / "app/plugins/sdk.d.ts"
    ).read_bytes()


@pytest.mark.parametrize("slot", ["assistant.toolbar", "assistant.above-prompt", "dashboard"])
async def test_removed_slot_is_rejected(slot: str) -> None:
    with pytest.raises(ValidationError, match="Unknown UI slot"):
        View(id="removed", title="Removed", slot=slot, entry="index.html")


async def test_editor_slot_presentation_and_icon_contract() -> None:
    view = View(
        id="editor",
        title="Editor",
        slot="editor.toolbar",
        renderer="declarative",
        render="ui.render",
        action="ui.action",
        icon="cloud-upload",
        presentation="popover",
    )
    assert view.icon == "CloudUpload"
    assert view.presentation == "popover"
    assert (
        View(
            id="default", title="Default", slot="editor.toolbar", entry="panel/index.html"
        ).presentation
        is None
    )
    with pytest.raises(ValidationError, match="Unknown Lucide"):
        View(
            id="invalid",
            title="Invalid",
            slot="editor.toolbar",
            entry="panel/index.html",
            icon="not-a-lucide-icon",
        )
    with pytest.raises(ValidationError, match=r"only supported in editor\.toolbar"):
        View(
            id="invalid",
            title="Invalid",
            entry="panel/index.html",
            presentation="dialog",
        )


async def test_editor_overlay_close_button() -> None:
    fields = {"id": "editor", "title": "Editor", "entry": "panel/index.html"}
    view = View.model_validate({**fields, "slot": "editor.toolbar", "showCloseButton": False})
    assert view.model_dump()["showCloseButton"] is False
    with pytest.raises(ValidationError, match=r"only supported in editor\.toolbar"):
        View.model_validate({**fields, "showCloseButton": False})


async def test_editor_toolbar_placement() -> None:
    fields = {"id": "editor", "title": "Editor", "entry": "panel/index.html"}
    for placement in ("left-end", "right-start", "right-end", None):
        view = View.model_validate(
            {**fields, "slot": "editor.toolbar", "placement": placement}
        )
        assert view.model_dump()["placement"] == placement
    with pytest.raises(ValidationError, match="only supported in editor.toolbar"):
        View.model_validate({**fields, "placement": "left-end"})
    with pytest.raises(ValidationError, match="placement"):
        View.model_validate(
            {**fields, "slot": "editor.toolbar", "placement": "left-start"}
        )


async def test_lucide_component_catalogue_and_validation():
    from app.plugins.declarative import CATALOGUE, resolve_component

    assert len(CATALOGUE["lucideIcons"]) > 1700
    assert "CloudUpload" in CATALOGUE["lucideIcons"]
    for component in ["Icon", "LucideIcon", "Project.Icon"]:
        assert resolve_component(component)[:2] == ("project", "Icon")
        document = validate_document(
            {
                "tree": {
                    "type": component,
                    "props": {
                        "name": "cloud-upload",
                        "size": 20,
                        "strokeWidth": 1.5,
                        "absoluteStrokeWidth": True,
                        "color": "var(--accent-11)",
                        "aria-label": "Upload",
                    },
                }
            }
        )
        assert document["trees"][0]["tree"]["props"]["name"] == "CloudUpload"
    for props in [
        {},
        {"name": "NoSuchIcon"},
        {"name": 1},
        {"name": "CloudUpload", "strokeWidth": "2"},
        {"name": "CloudUpload", "dangerouslySetInnerHTML": "bad"},
    ]:
        with pytest.raises(ValueError):
            validate_document({"tree": {"type": "Icon", "props": props}})
