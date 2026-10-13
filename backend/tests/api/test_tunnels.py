"""Tunnel lifecycle tests use real local subprocesses, without public connections."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

import app.tunnels as tunnels
from app.api.routers.tunnels import router
from app.auth import AUTH_COOKIE_NAME, AuthMiddleware, AuthService
from app.tunnels import TunnelManager, TunnelStart, public_url


@pytest.fixture
def launch(monkeypatch):
    original = asyncio.create_subprocess_exec
    calls = []

    def configure(
        output="https://test-tunnel.trycloudflare.com\nRegistered tunnel connection",
        lifetime=30,
    ):
        async def spawn(*args, **kwargs):
            calls.append((args, kwargs))
            script = (
                f"import time; print({output!r}, flush=True); time.sleep({lifetime})"
            )
            return await original(sys.executable, "-c", script, **kwargs)

        monkeypatch.setattr(tunnels, "executable", lambda provider: provider)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        return calls

    return configure


async def wait_status(manager, status):
    async with asyncio.timeout(3):
        while manager.status != status:
            await asyncio.sleep(0.01)


async def test_start_duplicate_stop_and_restart(launch):
    calls = launch()
    manager = TunnelManager()
    try:
        assert (await manager.start(TunnelStart(), 9123))["status"] == "starting"
        await wait_status(manager, "running")
        assert manager.url == "https://test-tunnel.trycloudflare.com"
        assert "http://127.0.0.1:9123" in calls[0][0]
        config_path = Path(calls[0][0][calls[0][0].index("--config") + 1])
        assert config_path.read_text() == "{}\n"
        with pytest.raises(ValueError, match="Stop the active"):
            await manager.start(TunnelStart(provider="ngrok"), 9123)
        process = manager.process
        assert (await manager.stop())["url"] is None
        assert process.returncode is not None
        assert not config_path.exists()
        launch(
            json.dumps({"msg": "started tunnel", "url": "https://test.ngrok-free.app"})
        )
        await manager.start(TunnelStart(provider="ngrok"), 9123)
        await wait_status(manager, "running")
        assert manager.url == "https://test.ngrok-free.app"
    finally:
        await manager.stop()


async def test_stop_before_monitor_runs(launch):
    launch()
    manager = TunnelManager()
    await manager.start(TunnelStart(), 8000)
    process = manager.process
    await manager.stop()
    assert process.returncode is not None
    assert manager.status == "stopped"


async def test_exit_clears_url(launch):
    launch(lifetime=0.2)
    manager = TunnelManager()
    try:
        await manager.start(TunnelStart(), 8000)
        await wait_status(manager, "running")
        await wait_status(manager, "error")
        assert manager.url is None
        assert manager.error == "process_exited"
    finally:
        await manager.stop()


async def test_timeout_terminates_process(launch, monkeypatch):
    launch(output="waiting")
    monkeypatch.setattr(tunnels, "STARTUP_TIMEOUT", 0.1)
    manager = TunnelManager()
    try:
        await manager.start(TunnelStart(), 8000)
        await wait_status(manager, "error")
        await manager.monitor
        assert manager.error == "startup_timeout"
        assert manager.process.returncode is not None
    finally:
        await manager.stop()


async def test_managed_token_not_in_arguments_or_snapshot(launch):
    calls = launch("Registered tunnel connection")
    manager = TunnelManager()
    try:
        await manager.start(
            TunnelStart(
                mode="managed-remote", token="private-token", hostname="fic.example.com"
            ),
            8000,
        )
        await wait_status(manager, "running")
        assert manager.url == "https://fic.example.com"
        assert calls[0][1]["env"]["TUNNEL_TOKEN"] == "private-token"
        assert "private-token" not in repr(calls[0][0])
        assert "private-token" not in repr(manager.snapshot())
    finally:
        await manager.stop()


@pytest.mark.parametrize(
    "payload",
    [
        {"provider": "other"},
        {"provider": "ngrok", "mode": "managed-remote"},
        {"mode": "managed-remote", "hostname": "fic.example.com"},
        {
            "mode": "managed-remote",
            "hostname": "https://fic.example.com",
            "token": "secret",
        },
    ],
)
def test_invalid_configuration(payload):
    with pytest.raises(ValidationError):
        TunnelStart(**payload)


def test_url_extraction_ignores_help_links():
    assert (
        public_url(
            "ngrok", json.dumps({"msg": "error", "url": "https://ngrok.com/docs"})
        )
        is None
    )
    assert public_url("cloudflare", "See https://developers.cloudflare.com") is None


async def test_api_password_gate_and_frontend_requirement(launch):
    calls = launch()
    app = FastAPI()
    service = AuthService(None)
    app.state.auth_service = service
    app.state.tunnel_manager = TunnelManager()
    app.state.tunnel_frontend_available = True
    app.include_router(router, prefix="/api/v1")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:9123"
    ) as client:
        assert (await client.get("/api/v1/tunnels")).json()["auth_enabled"] is False
        assert (await client.post("/api/v1/tunnels/start", json={})).status_code == 409
    service = AuthService("test-password")
    app.state.auth_service = service
    protected = AuthMiddleware(app, service, "/api/v1")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=protected), base_url="http://localhost:9123"
    ) as client:
        assert (await client.get("/api/v1/tunnels")).status_code == 401
        assert (await client.post("/api/v1/tunnels/start", json={})).status_code == 401
        client.cookies.set(AUTH_COOKIE_NAME, service.create_cookie_value())
        app.state.tunnel_frontend_available = False
        assert (await client.post("/api/v1/tunnels/start", json={})).status_code == 409
        app.state.tunnel_frontend_available = True
        assert (await client.post("/api/v1/tunnels/start", json={})).status_code == 200
        assert "http://127.0.0.1:9123" in calls[0][0]
        invalid = await client.post(
            "/api/v1/tunnels/start",
            json={
                "mode": "managed-remote",
                "token": "sensitive-token",
                "hostname": "bad",
            },
        )
        assert invalid.status_code == 422
        assert "sensitive-token" not in invalid.text
        assert (await client.post("/api/v1/tunnels/stop")).json()["status"] == "stopped"


async def test_missing_binary_and_launch_failure(launch, monkeypatch):
    manager = TunnelManager()
    monkeypatch.setattr(tunnels, "executable", lambda provider: None)
    with pytest.raises(ValueError, match="Install"):
        await manager.start(TunnelStart(), 8000)
    assert manager.status == "stopped"
    launch()

    async def failed_spawn(*args, **kwargs):
        raise OSError("cannot execute")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failed_spawn)
    result = await manager.start(TunnelStart(), 8000)
    assert result["status"] == "error"
    assert result["error"] == "launch_failed"
    assert manager.process is None
    assert (await manager.stop())["status"] == "stopped"


async def test_cloudflare_url_without_edge_connection_is_not_running(
    launch, monkeypatch
):
    launch(output="https://test-tunnel.trycloudflare.com")
    monkeypatch.setattr(tunnels, "STARTUP_TIMEOUT", 0.15)
    manager = TunnelManager()
    try:
        await manager.start(TunnelStart(), 8000)
        await asyncio.sleep(0.05)
        assert manager.status == "starting"
        assert manager.url is None
        await wait_status(manager, "error")
        await manager.monitor
        assert manager.error == "startup_timeout"
        assert manager.config_dir is None
    finally:
        await manager.stop()
