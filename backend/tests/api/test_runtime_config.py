# -*- coding: utf-8 -*-
"""runtime-config 端点与错误遥测设置 API 测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import settings as app_settings
from app.storage.repos import setting_repo
from app.telemetry import SETTING_KEY_TELEMETRY_ENABLED


@pytest.mark.asyncio
async def test_runtime_config_default_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "posthog_api_key", "phc_test_key")
    response = await client.get("/api/v1/runtime-config")
    assert response.status_code == 200
    data = response.json()
    assert data["posthog_enabled"] is True
    assert data["posthog_api_key"] == "phc_test_key"
    assert data["posthog_host"] == "https://us.i.posthog.com"


@pytest.mark.asyncio
async def test_runtime_config_disabled_when_setting_false(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "posthog_api_key", "phc_test_key")
    await setting_repo.upsert(session, SETTING_KEY_TELEMETRY_ENABLED, "false")
    await session.commit()

    response = await client.get("/api/v1/runtime-config")
    assert response.status_code == 200
    assert response.json()["posthog_enabled"] is False


@pytest.mark.asyncio
async def test_settings_telemetry_enabled_defaults_true(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["telemetry_enabled"] is True


@pytest.mark.asyncio
async def test_settings_telemetry_enabled_update(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.patch("/api/v1/settings", json={"telemetry_enabled": False})
    assert response.status_code == 200
    assert response.json()["telemetry_enabled"] is False

    setting = await setting_repo.get_by_key(session, SETTING_KEY_TELEMETRY_ENABLED)
    assert setting is not None
    assert setting.value == "false"
