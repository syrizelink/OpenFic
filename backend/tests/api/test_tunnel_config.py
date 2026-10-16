"""隧道配置持久化测试。"""

import asyncio
import sys

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.tunnels import router
from app.auth import AuthService
from app.storage.database import get_session
from app.storage.repos import setting_repo
from app.tunnels import TunnelManager
from app.tunnels_config import SETTING_KEY_TUNNEL_CONFIG, parse_tunnel_config


@pytest.fixture
def launch(monkeypatch):
    original = asyncio.create_subprocess_exec

    def configure(output="Registered tunnel connection", lifetime=30):
        async def spawn(*args, **kwargs):
            script = f"import time; print({output!r}, flush=True); time.sleep({lifetime})"
            return await original(sys.executable, "-c", script, **kwargs)

        monkeypatch.setattr("app.tunnels.executable", lambda provider: provider)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    return configure


@pytest.mark.asyncio
async def test_tunnel_config_encrypts_token_and_reuses_it(
    db_engine, launch
) -> None:
    app = FastAPI()
    app.state.auth_service = AuthService("test-password")
    app.state.tunnel_manager = TunnelManager()
    app.state.tunnel_frontend_available = True
    app.include_router(router, prefix="/api/v1")

    launch("Registered tunnel connection")
    async with db_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)

        async def override_get_session():
            yield session

        app.dependency_overrides[get_session] = override_get_session
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://localhost:9123",
            ) as client:
                response = await client.put(
                    "/api/v1/tunnels/config",
                    json={
                        "provider": "cloudflare",
                        "mode": "managed-remote",
                        "hostname": "fic.example.com",
                        "token": "private-token",
                    },
                )
                assert response.status_code == 200
                assert response.json() == {
                    "provider": "cloudflare",
                    "mode": "managed-remote",
                    "hostname": "fic.example.com",
                    "token_configured": True,
                }
                assert "private-token" not in response.text

                setting = await setting_repo.get_by_key(session, SETTING_KEY_TUNNEL_CONFIG)
                assert setting is not None
                assert "private-token" not in setting.value
                assert parse_tunnel_config(setting.value).token == "private-token"

                response = await client.get("/api/v1/tunnels")
                assert response.status_code == 200
                assert response.json()["config"] == {
                    "provider": "cloudflare",
                    "mode": "managed-remote",
                    "hostname": "fic.example.com",
                    "token_configured": True,
                }
                assert "private-token" not in response.text

                response = await client.post(
                    "/api/v1/tunnels/start",
                    json={
                        "provider": "cloudflare",
                        "mode": "managed-remote",
                        "hostname": "fic.example.com",
                    },
                )
                assert response.status_code == 200
                assert response.json()["status"] == "starting"
                assert response.json().get("token") is None
                assert response.json().get("config") is None
                assert app.state.tunnel_manager.process is not None
                assert (
                    app.state.tunnel_manager.process is not None
                    and app.state.tunnel_manager.process.returncode is None
                )
                await app.state.tunnel_manager.stop()
        finally:
            await session.close()
            await connection.rollback()
