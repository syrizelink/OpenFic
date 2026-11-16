"""Contract and lifecycle tests using actual installable plugin packages."""

import io
import json
import stat
import sys
import zipfile
from pathlib import Path

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
):
    output = io.BytesIO()
    manifest = json.loads((SOURCE / "plugin.json").read_text())
    manifest["version"] = version
    manifest["id"] = plugin_id
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
