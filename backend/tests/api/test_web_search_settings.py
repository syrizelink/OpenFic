# -*- coding: utf-8 -*-
"""联网搜索设置 API 测试。"""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools.impls.web_search.config import (
    SETTING_KEY_WEB_SEARCH_CONFIG,
    parse_web_search_settings,
)
from app.storage.repos import setting_repo


@pytest.mark.asyncio
async def test_get_web_search_settings_default(client: AsyncClient) -> None:
    """默认情况下联网搜索关闭且未配置 provider。"""
    response = await client.get("/api/v1/settings/web-search")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["provider"] == ""
    assert data["has_api_key"] is False
    assert data["extras"] == {}


@pytest.mark.asyncio
async def test_get_web_search_providers(client: AsyncClient) -> None:
    """provider 列表包含后端全部 provider 且按字母序排列。"""
    response = await client.get("/api/v1/settings/web-search/providers")
    assert response.status_code == 200
    data = response.json()
    names = [item["name"] for item in data]
    assert names == sorted(names)
    assert names == [
        "bing",
        "brave",
        "ddgs",
        "exa",
        "jina",
        "perplexity",
        "searxng",
        "serper",
        "tavily",
        "zhipu",
    ]
    by_name = {item["name"]: item for item in data}
    assert by_name["ddgs"]["requires_api_key"] is False
    assert by_name["searxng"]["requires_api_key"] is False
    assert by_name["tavily"]["requires_api_key"] is True


@pytest.mark.asyncio
async def test_update_web_search_settings(client: AsyncClient, session: AsyncSession) -> None:
    """更新联网搜索设置后 API Key 加密存储、响应不回传明文。"""
    response = await client.put(
        "/api/v1/settings/web-search",
        json={
            "enabled": True,
            "provider": "tavily",
            "api_key": "secret-key",
            "extras": {},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["provider"] == "tavily"
    assert data["has_api_key"] is True
    assert "secret-key" not in response.text

    setting = await setting_repo.get_by_key(session, SETTING_KEY_WEB_SEARCH_CONFIG)
    assert setting is not None
    assert "secret-key" not in setting.value
    config = parse_web_search_settings(setting.value)
    assert config.enabled is True
    assert config.provider == "tavily"
    assert config.api_key == "secret-key"


@pytest.mark.asyncio
async def test_update_web_search_settings_keeps_api_key_when_omitted(
    client: AsyncClient, session: AsyncSession
) -> None:
    """api_key 不传时保持原有 Key 不变。"""
    await client.put(
        "/api/v1/settings/web-search",
        json={"enabled": True, "provider": "serper", "api_key": "keep-me"},
    )
    response = await client.put(
        "/api/v1/settings/web-search",
        json={"enabled": False, "provider": "serper"},
    )
    assert response.status_code == 200
    assert response.json()["has_api_key"] is True

    setting = await setting_repo.get_by_key(session, SETTING_KEY_WEB_SEARCH_CONFIG)
    assert parse_web_search_settings(setting.value).api_key == "keep-me"


@pytest.mark.asyncio
async def test_update_web_search_settings_clears_api_key_with_empty_string(
    client: AsyncClient, session: AsyncSession
) -> None:
    """api_key 传空字符串时清除原有 Key。"""
    await client.put(
        "/api/v1/settings/web-search",
        json={"enabled": True, "provider": "serper", "api_key": "clear-me"},
    )
    response = await client.put(
        "/api/v1/settings/web-search",
        json={"api_key": ""},
    )
    assert response.status_code == 200
    assert response.json()["has_api_key"] is False

    setting = await setting_repo.get_by_key(session, SETTING_KEY_WEB_SEARCH_CONFIG)
    assert parse_web_search_settings(setting.value).api_key == ""


@pytest.mark.asyncio
async def test_update_web_search_settings_rejects_unknown_provider(
    client: AsyncClient,
) -> None:
    """不支持的 provider 返回 400。"""
    response = await client.put(
        "/api/v1/settings/web-search",
        json={"provider": "google"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_web_search_settings_filters_unknown_extras(
    client: AsyncClient, session: AsyncSession
) -> None:
    """extras 中不属于当前 provider 的键会被过滤。"""
    response = await client.put(
        "/api/v1/settings/web-search",
        json={
            "enabled": True,
            "provider": "bing",
            "extras": {"bing_mkt": "en-US", "not_a_field": "x"},
        },
    )
    assert response.status_code == 200
    assert response.json()["extras"] == {"bing_mkt": "en-US"}

    setting = await setting_repo.get_by_key(session, SETTING_KEY_WEB_SEARCH_CONFIG)
    assert json.loads(setting.value)["extras"] == {"bing_mkt": "en-US"}


@pytest.mark.asyncio
async def test_update_web_search_settings_switching_provider_clears_extras(
    client: AsyncClient, session: AsyncSession
) -> None:
    """切换 provider 且未携带 extras 时，旧 provider 的扩展参数被清除。"""
    await client.put(
        "/api/v1/settings/web-search",
        json={
            "enabled": True,
            "provider": "bing",
            "extras": {"bing_mkt": "en-US"},
        },
    )
    response = await client.put(
        "/api/v1/settings/web-search",
        json={"provider": "ddgs"},
    )
    assert response.status_code == 200
    assert response.json()["extras"] == {}

    setting = await setting_repo.get_by_key(session, SETTING_KEY_WEB_SEARCH_CONFIG)
    assert json.loads(setting.value)["extras"] == {}
