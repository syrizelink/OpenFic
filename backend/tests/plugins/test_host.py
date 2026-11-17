"""Contract and lifecycle tests using actual installable plugin packages."""

import asyncio
import io
import json
import stat
import sys
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers.plugins import router, asset_router
from app.auth import AuthMiddleware, AuthService
from app.plugins.host import PluginError, PluginHost
from app.storage.database import get_session

SOURCE = Path(__file__).resolve().parents[3] / "examples/plugins/project-statistics"
pytestmark = pytest.mark.asyncio(loop_scope="module")


def package(
    version="1.0.0",
    backend=None,
    capabilities=None,
    *,
    legacy=False,
    plugin_id="project-statistics",
    settings=None,
    detail=None,
    extra_files=None,
    icon=None,
    homepage=None,
):
    output = io.BytesIO()
    manifest = json.loads((SOURCE / "plugin.json").read_text())
    manifest["version"] = version
    manifest["id"] = plugin_id
    if settings is not None:
        manifest["settings"] = settings
    if detail is not None:
        manifest["detail"] = detail
    if icon is not None:
        manifest["icon"] = icon
    if homepage is not None:
        manifest["homepage"] = homepage
    # Keep iframe ticket/CSP lifecycle coverage independent of the native example UI.
    manifest["views"] = [
        {
            "id": "overview",
            "title": "项目统计",
            "entry": "panel/index.html",
            "slot": "sidebar.extensions",
        }
    ]
    manifest["resources"] = ["panel"]
    if capabilities is not None:
        manifest["capabilities"] = capabilities
    if legacy:
        manifest["backend"] = "backend/main.py"
        manifest.pop("entry", None)
        manifest.pop("resources", None)
        manifest["views"][0]["entry"] = "frontend/index.html"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (extra_files or {}).items():
            archive.writestr(name, content)
        archive.writestr(
            manifest["views"][0]["entry"],
            "<!doctype html><main>Legacy transport fixture</main>",
        )
        for path in sorted(SOURCE.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = path.relative_to(SOURCE).as_posix()
            content = path.read_bytes()
            if name == "plugin.json":
                content = json.dumps(manifest).encode()
            if name == "main.py" and backend is not None:
                content = backend.encode()
            archive.writestr(
                "backend/main.py" if legacy and name == "main.py" else name, content
            )
    return output.getvalue()


@pytest_asyncio.fixture
async def plugin_api(tmp_path, session):
    manager = PluginHost(tmp_path / "plugins")
    await manager.start()
    app = FastAPI()
    app.state.plugin_host = manager
    app.include_router(router, prefix="/api/v1")
    app.include_router(asset_router)

    async def get_db():
        yield session

    app.dependency_overrides[get_session] = get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield manager, client, app
    await manager.close()


async def install(client, content=None):
    return await client.post(
        "/api/v1/plugins",
        files={"file": ("plugin.zip", content or package(), "application/zip")},
        data={"trusted": "true"},
    )


async def test_plugin_homepage_and_local_icon(plugin_api):
    host, api, _ = plugin_api
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 20"><rect width="30" height="20"/></svg>'
    response = await install(
        api,
        package(
            icon="images/icon.svg",
            homepage="https://github.com/example/plugin",
            extra_files={"images/icon.svg": svg},
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["icon"] == "images/icon.svg"
    assert response.json()["homepage"] == "https://github.com/example/plugin"
    image = await api.get("/api/v1/plugins/project-statistics/icon")
    assert image.status_code == 200 and image.content == svg
    assert image.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in image.headers["content-security-policy"]
    await host.close()
    await host.start()
    assert (await api.get("/api/v1/plugins/project-statistics/icon")).content == svg


async def test_plugin_icon_accepts_self_contained_svg_at_size_limit(plugin_api):
    _, api, _ = plugin_api
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" aria-label="author@example.org">
    <style>/* local styles */ @media (prefers-color-scheme: dark) { .shape { fill: url(#gradient); } }</style>
    <defs><linearGradient id="gradient"><stop stop-color="red"/></linearGradient></defs>
    <rect class="shape" width="16" height="16"><animate attributeName="opacity" values="0;1" dur="1s"/></rect></svg>"""
    svg += b" " * (256 * 1024 - len(svg))
    response = await install(
        api, package(icon="icon.svg", extra_files={"icon.svg": svg})
    )
    assert response.status_code == 201
    assert (await api.get("/api/v1/plugins/project-statistics/icon")).content == svg


async def test_plugin_icon_accepts_embedded_raster_image(plugin_api):
    import base64

    from PIL import Image

    _, api, _ = plugin_api
    image = io.BytesIO()
    Image.new("RGB", (2, 1), "red").save(image, format="PNG")
    embedded = base64.b64encode(image.getvalue()).decode()
    svg = f'<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,{embedded}" width="2" height="1"/></svg>'.encode()
    response = await install(
        api, package(icon="icon.svg", extra_files={"icon.svg": svg})
    )
    assert response.status_code == 201
    assert (await api.get("/api/v1/plugins/project-statistics/icon")).content == svg


@pytest.mark.parametrize(
    ("icon", "content"),
    [
        ("../outside.svg", b""),
        ("https://example.com/icon.svg", b""),
        ("icon.txt", b"text"),
        ("icon.png", b"not a PNG"),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>',
        ),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><style>@import "https://example.com/a.css";</style></svg>',
        ),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(https://example.com/a)"/></svg>',
        ),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        ),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><style>.x { fill: image-set("https://example.com/a.png" 1x) }</style></svg>',
        ),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><image><set attributeName="href" to="https://example.com/a.png"/></image></svg>',
        ),
        (
            "icon.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"/>' + b" " * (256 * 1024),
        ),
    ],
    ids=[
        "traversal",
        "remote",
        "extension",
        "invalid-png",
        "external-image",
        "external-css",
        "external-paint",
        "script",
        "external-image-set",
        "animated-external-reference",
        "oversized",
    ],
)
async def test_invalid_icon_does_not_prevent_installation(plugin_api, icon, content):
    _, api, _ = plugin_api
    extra_files = {icon: content} if not icon.startswith(("..", "https:")) else {}
    response = await install(api, package(icon=icon, extra_files=extra_files))
    assert response.status_code == 201, response.text
    assert (await api.get("/api/v1/plugins/project-statistics/icon")).status_code == 404


@pytest.mark.parametrize(
    ("suffix", "format"),
    [
        ("png", "PNG"),
        ("PNG", "PNG"),
        ("jpg", "JPEG"),
        ("jpeg", "JPEG"),
        ("webp", "WEBP"),
    ],
)
async def test_raster_plugin_icon_formats(plugin_api, suffix, format):
    from PIL import Image

    _, api, _ = plugin_api
    image = io.BytesIO()
    Image.new("RGB", (8, 4), "red").save(image, format=format)
    response = await install(
        api,
        package(
            icon=f"icon.{suffix}", extra_files={f"icon.{suffix}": image.getvalue()}
        ),
    )
    assert response.status_code == 201, response.text
    result = await api.get("/api/v1/plugins/project-statistics/icon")
    assert result.status_code == 200 and result.content == image.getvalue()


async def test_plugin_detail_readme_and_images(plugin_api):
    host, api, _ = plugin_api
    content = package(
        extra_files={
            "ReadMe.MD": "# Details\n![pic](assets/pic.png)",
            "assets/pic.png": b"image",
        }
    )
    response = await install(api, content)
    assert response.status_code == 201, response.text
    assert response.json()["detail"] == "ReadMe.MD"
    assert (await api.get("/api/v1/plugins/project-statistics/detail")).text.startswith(
        "# Details"
    )
    image = await api.get(
        "/api/v1/plugins/project-statistics/detail-images/assets/pic.png"
    )
    assert image.status_code == 200 and image.content == b"image"
    assert "sandbox" in image.headers["content-security-policy"]
    assert (
        await api.get("/api/v1/plugins/project-statistics/detail-images/main.py")
    ).status_code == 404
    await host.close()
    await host.start()
    assert (await api.get("/api/v1/plugins")).json()["plugins"][0][
        "detail"
    ] == "ReadMe.MD"


@pytest.mark.parametrize("detail", ["../README.md", "docs/missing.md", "main.py"])
async def test_plugin_detail_rejects_invalid_path(plugin_api, detail):
    _, api, _ = plugin_api
    response = await install(api, package(detail=detail))
    assert response.status_code == 400


async def test_plugin_detail_explicit_file_takes_precedence(plugin_api):
    _, api, _ = plugin_api
    response = await install(
        api,
        package(
            detail="docs/guide.md",
            extra_files={"README.md": "default", "docs/guide.md": "# Guide"},
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["detail"] == "docs/guide.md"
    assert (
        await api.get("/api/v1/plugins/project-statistics/detail")
    ).text == "# Guide"


async def test_plugin_without_detail_has_no_detail_endpoint(plugin_api):
    _, api, _ = plugin_api
    response = await install(api, package())
    assert response.status_code == 201
    assert response.json()["detail"] is None
    assert (
        await api.get("/api/v1/plugins/project-statistics/detail")
    ).status_code == 404


async def test_required_settings_allow_install_but_validate_saves(plugin_api):
    host, api, _ = plugin_api
    settings = [
        {
            "key": "name",
            "label": "Name",
            "type": "string",
            "default": "",
            "required": True,
        },
        {
            "key": "token",
            "label": "Token",
            "type": "string",
            "default": "",
            "secret": True,
            "required": True,
        },
        {
            "key": "payload",
            "label": "Payload",
            "type": "json",
            "default": None,
            "required": True,
        },
        {
            "key": "count",
            "label": "Count",
            "type": "integer",
            "default": 0,
            "required": True,
        },
        {
            "key": "enabled",
            "label": "Enabled",
            "type": "boolean",
            "default": False,
            "required": True,
        },
        {
            "key": "secretCount",
            "label": "Secret count",
            "type": "integer",
            "default": 0,
            "secret": True,
            "required": True,
        },
        {
            "key": "secretFlag",
            "label": "Secret flag",
            "type": "boolean",
            "default": False,
            "secret": True,
            "required": True,
        },
        {
            "key": "mode",
            "label": "Mode",
            "type": "select",
            "default": "fast",
            "required": True,
            "options": [{"value": "fast", "label": "Fast"}],
        },
        {"key": "optional", "label": "Optional", "type": "string", "default": ""},
    ]
    response = await install(api, package(settings=settings))
    assert response.status_code == 201, response.text
    assert response.json()["settings"][0]["required"] is True
    assert {"secretCount", "secretFlag"} <= set(response.json()["configured_secrets"])
    await host.close()
    await host.start()
    assert len((await api.get("/api/v1/plugins")).json()["plugins"]) == 1
    path = "/api/v1/plugins/project-statistics/settings"
    valid = {
        "name": "Ready",
        "token": "secret",
        "payload": {},
        "count": 0,
        "enabled": False,
        "mode": "fast",
        "optional": "",
    }
    for changes in ({"name": "  "}, {"token": ""}, {"payload": None}):
        result = await api.put(path, json={"settings": valid | changes})
        assert result.status_code == 400
    assert (await api.put(path, json={"settings": valid})).status_code == 200
    preserved = await api.put(path, json={"settings": valid | {"token": ""}})
    assert preserved.status_code == 200
    assert "token" in preserved.json()["configured_secrets"]
    assert preserved.json()["configuration"]["token"] == ""


async def test_select_setting_validation_and_persistence(plugin_api):
    host, api, _ = plugin_api
    setting = {
        "key": "mode",
        "label": "Mode",
        "type": "select",
        "default": "fast",
        "options": [
            {"value": "fast", "label": "Fast"},
            {"value": "precise", "label": "Precise"},
        ],
    }
    response = await install(api, package(settings=[setting]))
    assert response.status_code == 201, response.text
    assert response.json()["settings"][0]["options"] == setting["options"]
    assert (
        await api.put(
            "/api/v1/plugins/project-statistics/settings",
            json={"settings": {"mode": "precise"}},
        )
    ).status_code == 200
    assert (
        await api.put(
            "/api/v1/plugins/project-statistics/settings",
            json={"settings": {"mode": "invalid"}},
        )
    ).status_code == 400
    await host.close()
    await host.start()
    assert (await api.get("/api/v1/plugins")).json()["plugins"][0]["configuration"][
        "mode"
    ] == "precise"


@pytest.mark.parametrize(
    "changes",
    [
        {"options": []},
        {
            "options": [
                {"value": "fast", "label": "Fast"},
                {"value": "fast", "label": "Duplicate"},
            ]
        },
        {"default": "missing"},
    ],
)
async def test_select_rejects_invalid_definitions(plugin_api, changes):
    _, api, _ = plugin_api
    setting = {
        "key": "mode",
        "label": "Mode",
        "type": "select",
        "default": "fast",
        "options": [{"value": "fast", "label": "Fast"}],
    } | changes
    response = await install(api, package(settings=[setting]))
    assert response.status_code == 400


async def test_plugin_changes_are_pushed_after_lifecycle_writes(
    plugin_api, monkeypatch
):
    host, _, _ = plugin_api
    send = AsyncMock()
    monkeypatch.setattr("app.socket.emitter.emit", send)

    async def changed(action):
        await action
        await asyncio.wait_for(host._notifications.join(), 5)
        assert any(
            call.args == ("plugins:changed", {}) for call in send.await_args_list
        )
        send.reset_mock()

    await changed(host.install(package()))
    await changed(host.set_enabled("project-statistics", True))
    await changed(host.configure("project-statistics", {"targetWords": 1234}))
    await changed(host.set_order(["project-statistics"]))
    await changed(host.install(package("1.1.0"), update_id="project-statistics"))
    await changed(host.set_enabled("project-statistics", False))
    await changed(host.uninstall("project-statistics"))
    assert not any(route.path == "/plugins/events" for route in router.routes)


async def test_plugin_events_push_live_and_stop_cleanly(plugin_api, monkeypatch):
    host, _, _ = plugin_api
    send = AsyncMock()
    monkeypatch.setattr("app.socket.emitter.emit", send)
    host.emit("ui.invalidate", {"viewId": "panel"}, "example")
    await asyncio.wait_for(host._notifications.join(), 5)
    send.assert_awaited_once_with(
        "plugins:event",
        {
            "event": "ui.invalidate",
            "data": {"viewId": "panel"},
            "pluginId": "example",
        },
    )
    task = host._notification_task
    await host.close()
    assert task.done()
    send.reset_mock()
    host.emit("ui.toast", {"text": "closed"})
    await host.start()
    await asyncio.wait_for(host._notifications.join(), 5)
    send.assert_not_awaited()


async def test_plugin_notification_overflow_requests_resync(plugin_api, monkeypatch):
    host, _, _ = plugin_api
    entered = asyncio.Event()
    release = asyncio.Event()
    sent = []

    async def send(event, data):
        entered.set()
        await release.wait()
        sent.append((event, data))

    monkeypatch.setattr("app.socket.emitter.emit", send)
    host.emit("ui.invalidate", {})
    await asyncio.wait_for(entered.wait(), 5)
    for index in range(host._notifications.maxsize + 1):
        host.emit("ui.invalidate", {"index": index})
    assert host._notifications.qsize() <= host._notifications.maxsize
    release.set()
    await asyncio.wait_for(host._notifications.join(), 5)
    assert ("plugins:resync", {}) in sent
    assert sent[-1][1]["data"]["index"] == host._notifications.maxsize


async def test_plugin_order_survives_update_install_restart_and_uninstall(
    plugin_api, monkeypatch
):
    host, api, _ = plugin_api
    for plugin_id in ["alpha", "zeta"]:
        assert (await install(api, package(plugin_id=plugin_id))).status_code == 201
        await host.set_enabled(plugin_id, True)
    response = await api.put(
        "/api/v1/plugins/order", json={"plugin_ids": ["zeta", "alpha"]}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"plugin_ids": ["zeta", "alpha"]}
    assert [p["id"] for p in (await api.get("/api/v1/plugins")).json()["plugins"]] == [
        "zeta",
        "alpha",
    ]
    await host.install(package("1.1.0", plugin_id="alpha"), update_id="alpha")
    await host.install(package(plugin_id="beta"))
    assert list(host.plugins) == ["zeta", "alpha", "beta"]
    await host.close()
    activation_order = []
    activate = host._activate

    async def record_activation(plugin):
        activation_order.append(plugin.manifest.id)
        await activate(plugin)

    monkeypatch.setattr(host, "_activate", record_activation)
    await host.start()
    assert list(host.plugins) == ["zeta", "alpha", "beta"]
    assert activation_order == ["zeta", "alpha"]
    assert host.get("alpha").manifest.version == "1.1.0"
    await host.uninstall("alpha")
    await host.close()
    await host.start()
    assert list(host.plugins) == ["zeta", "beta"]


@pytest.mark.parametrize(
    "plugin_ids", [["alpha"], ["alpha", "alpha"], ["alpha", "unknown"]]
)
async def test_invalid_plugin_order_leaves_registry_unchanged(plugin_api, plugin_ids):
    host, api, _ = plugin_api
    for plugin_id in ["alpha", "zeta"]:
        await install(api, package(plugin_id=plugin_id))
    registry = (host.root / ".registry.json").read_bytes()
    response = await api.put("/api/v1/plugins/order", json={"plugin_ids": plugin_ids})
    assert response.status_code == 400, response.text
    assert list(host.plugins) == ["alpha", "zeta"]
    assert (host.root / ".registry.json").read_bytes() == registry


async def test_plugin_order_write_failure_restores_memory(plugin_api, monkeypatch):
    host, api, _ = plugin_api
    for plugin_id in ["alpha", "zeta"]:
        await install(api, package(plugin_id=plugin_id))
    registry = (host.root / ".registry.json").read_bytes()

    def fail_persist():
        raise OSError("disk full")

    monkeypatch.setattr(host, "_persist", fail_persist)
    with pytest.raises(OSError, match="disk full"):
        await host.set_order(["zeta", "alpha"])
    assert list(host.plugins) == ["alpha", "zeta"]
    assert (host.root / ".registry.json").read_bytes() == registry


async def test_install_enable_statistics_configuration_restart_export_uninstall(
    plugin_api, client, session
):
    host, api, _ = plugin_api
    project = (await client.post("/api/v1/projects", data={"title": "统计验证"})).json()
    project_id = project["id"]
    volume = (await client.get(f"/api/v1/projects/{project_id}/volumes")).json()[0]
    for title, count in [("一", 100), ("二", 300)]:
        response = await client.post(
            f"/api/v1/projects/{project_id}/chapters",
            json={
                "volume_id": volume["id"],
                "title": title,
                "content": "内容",
                "word_count": count,
            },
        )
        assert response.status_code == 201
    from app.storage.models.character import Character
    from app.storage.models.note import Note
    from app.storage.models.world_info import WorldInfo
    from app.storage.models.world_info_entry import WorldInfoEntry

    world = WorldInfo(project_id=project_id, name="世界")
    session.add(world)
    await session.flush()
    session.add_all(
        [
            Character(project_id=project_id, name="角色"),
            Note(project_id=project_id, title="笔记"),
            WorldInfoEntry(world_info_id=world.id, uid=1, name="条目", order=1),
        ]
    )
    await session.flush()

    response = await install(api)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "disabled"
    assert (await install(api)).status_code == 409
    assert (
        await api.post(
            "/api/v1/plugins/project-statistics/rpc", json={"method": "projects.list"}
        )
    ).status_code == 409
    enabled = await api.patch(
        "/api/v1/plugins/project-statistics/enabled", json={"enabled": True}
    )
    assert enabled.json()["commands"] == [
        "projects.list",
        "statistics.get",
        "ui.action",
        "ui.render",
    ]
    asset = await api.get("/api/v1/plugins/project-statistics/assets/panel/index.html")
    assert asset.status_code == 200
    assert "connect-src 'none'" in asset.headers["content-security-policy"]
    assert (
        await api.get("/api/v1/plugins/project-statistics/assets/main.py")
    ).status_code == 404
    stats = await api.post(
        "/api/v1/plugins/project-statistics/rpc",
        json={"method": "statistics.get", "params": {"projectId": project_id}},
    )
    assert stats.status_code == 200, stats.text
    data = stats.json()["result"]
    assert (data["words"], data["chapters"], data["averageChapterWords"]) == (
        400,
        2,
        200,
    )
    assert (data["characters"], data["notes"], data["worldEntries"]) == (1, 1, 1)
    assert data["volumeDistribution"][0]["words"] == 400
    configured = await api.put(
        "/api/v1/plugins/project-statistics/settings",
        json={"settings": {"targetWords": 800, "showVolumes": False}},
    )
    assert configured.status_code == 200
    assert (
        await api.put(
            "/api/v1/plugins/project-statistics/settings",
            json={"settings": {"targetWords": True}},
        )
    ).status_code == 400
    assert (
        await api.put(
            "/api/v1/plugins/project-statistics/settings",
            json={"settings": {"targetWords": 0}},
        )
    ).status_code == 400
    await host.close()
    await host.start()
    result = await host.call(
        "project-statistics", "statistics.get", {"projectId": project_id}, session
    )
    assert result["progress"] == 50
    assert result["volumeDistribution"] == []
    exported = await api.get("/api/v1/plugins/project-statistics/package")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert "plugin.json" in archive.namelist()
        assert not any("__pycache__" in name for name in archive.namelist())
    assert (
        await api.patch(
            "/api/v1/plugins/project-statistics/enabled", json={"enabled": False}
        )
    ).status_code == 200
    assert (
        await api.get("/api/v1/plugins/project-statistics/assets/panel/index.html")
    ).status_code == 409
    assert (await api.delete("/api/v1/plugins/project-statistics")).status_code == 204
    assert (await api.get("/api/v1/plugins")).json()["plugins"] == []
    assert not (host.root / "project-statistics").exists()
    assert (await install(api, exported.content)).status_code == 201


async def test_update_failure_rolls_back_and_disposes_commands(plugin_api, session):
    host, api, _ = plugin_api
    await install(api)
    await host.set_enabled("project-statistics", True)
    old_module = host.get("project-statistics").module_name
    assert old_module in sys.modules
    failed = await api.put(
        "/api/v1/plugins/project-statistics/package",
        files={
            "file": (
                "update.zip",
                package(
                    "1.1.0",
                    "def register(host):\n    raise RuntimeError('broken update')\n",
                ),
            )
        },
        data={"trusted": "true"},
    )
    assert failed.status_code == 400
    assert host.get("project-statistics").manifest.version == "1.0.0"
    assert host.get("project-statistics").registration is not None
    assert old_module not in sys.modules
    success = await api.put(
        "/api/v1/plugins/project-statistics/package",
        files={"file": ("update.zip", package("1.1.0"))},
        data={"trusted": "true"},
    )
    assert success.status_code == 200, success.text
    assert success.json()["version"] == "1.1.0"
    assert len(host.get("project-statistics").registration.commands) == 4
    assert (await api.get("/api/v1/plugins/project-statistics/logs")).json()[-1][
        "action"
    ] == "update"
    assert (
        await api.put(
            "/api/v1/plugins/project-statistics/package",
            files={"file": ("old.zip", package())},
            data={"trusted": "true"},
        )
    ).status_code == 409


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "frontend/../../escape",
        "frontend\\escape",
        "C:/escape",
    ],
)
async def test_archive_traversal_rejected(plugin_api, name):
    host, api, _ = plugin_api
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, "bad")
    response = await install(api, output.getvalue())
    assert response.status_code == 400
    assert not host.plugins
    assert not list(host.root.glob(".install-*"))


async def test_invalid_contract_symlink_and_missing_capability(plugin_api, session):
    host, api, _ = plugin_api
    assert (
        await api.post("/api/v1/plugins", files={"file": ("plugin.zip", package())})
    ).status_code == 400
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        link = zipfile.ZipInfo("frontend/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "../main.py")
    assert (await install(api, output.getvalue())).status_code == 400
    assert (await install(api, b"invalid zip")).status_code == 400
    await install(api, package(capabilities=[]))
    await host.set_enabled("project-statistics", True)
    with pytest.raises(PluginError, match="projects.read"):
        await host.call("project-statistics", "projects.list", {}, session)
    assert host.logs("project-statistics")[-1]["level"] == "error"


async def test_authentication_protects_management_rpc_and_assets(plugin_api):
    _, _, app = plugin_api
    auth = AuthService("test-password")
    app.add_middleware(AuthMiddleware, auth_service=auth, api_prefix="/api/v1")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for path in [
            "/api/v1/plugins",
            "/api/v1/plugins/sdk.js",
            "/api/v1/plugins/project-statistics/assets/panel/index.html",
        ]:
            assert (await client.get(path)).status_code == 401
        client.cookies.set("openfic_auth", auth.create_cookie_value())
        assert (await client.get("/api/v1/plugins")).status_code == 200
        await install(client)
        await client.patch(
            "/api/v1/plugins/project-statistics/enabled", json={"enabled": True}
        )
        opened = await client.post("/api/v1/plugins/project-statistics/views/overview")
        url = opened.json()["url"]
        client.cookies.clear()
        assert (await client.get(url)).status_code == 200
        token = url.split("/")[2]
        assert (await client.get(f"/plugin-assets/{token}/sdk.js")).status_code == 200
        assert (
            await client.get(f"/plugin-assets/{token}/other/assets/index.html")
        ).status_code == 404
        assert (await client.get("/plugin-assets/invalid/sdk.js")).status_code == 404
        assert (
            await client.post(
                "/api/v1/plugins/project-statistics/rpc",
                json={"method": "projects.list"},
            )
        ).status_code == 401
        host = app.state.plugin_host
        await host.set_enabled("project-statistics", False)
        assert (await client.get(url)).status_code == 404


async def test_asset_tickets_are_redacted_from_access_logs():
    from app.api.middleware.access_log import redact_plugin_asset_path

    assert (
        redact_plugin_asset_path("/plugin-assets/secret/id/assets/index.html")
        == "/plugin-assets/[ticket]/id/assets/index.html"
    )
    assert redact_plugin_asset_path("/api/v1/plugins") == "/api/v1/plugins"


async def test_update_file_swap_failure_restores_active_plugin(plugin_api, monkeypatch):
    host, api, _ = plugin_api
    await install(api)
    await host.set_enabled("project-statistics", True)
    original_replace = Path.replace

    def fail_stage_swap(path, target):
        if path.name.startswith(".install-"):
            raise OSError("simulated file swap failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_stage_swap)
    with pytest.raises(PluginError, match="previous state restored"):
        await host.install(package("1.1.0"), update_id="project-statistics")
    restored = host.get("project-statistics")
    assert restored.manifest.version == "1.0.0"
    assert restored.registration is not None
    assert (host.root / "project-statistics/plugin.json").exists()
    assert not list(host.root.glob(".backup-*"))
    assert not list(host.root.glob(".install-*"))


async def test_expired_view_ticket_and_oversized_rpc_rejected(plugin_api):
    host, api, _ = plugin_api
    await install(api)
    await host.set_enabled("project-statistics", True)
    opened = await api.post("/api/v1/plugins/project-statistics/views/overview")
    url = opened.json()["url"]
    token = url.split("/")[2]
    host._view_tickets[token] = ("project-statistics", 0)
    assert (await api.get(url)).status_code == 404
    response = await api.post(
        "/api/v1/plugins/project-statistics/rpc",
        json={"method": "projects.list", "params": {"payload": "x" * 64001}},
    )
    assert response.status_code == 422
