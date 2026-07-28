# -*- coding: utf-8 -*-
"""
Catalog icon proxy service tests.
"""

import httpx
import pytest

from app.models.catalog.icon_proxy import CatalogIconProxyService


class _FakeClient:
    def __init__(self, responder):
        self._responder = responder

    async def get(self, url: str) -> httpx.Response:
        return await self._responder(url)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_fetches_jsdelivr_before_models_dev_for_each_icon() -> None:
    calls: list[str] = []

    async def responder(url: str) -> httpx.Response:
        if "providers/openai/logo.svg" in url:
            calls.append("jsdelivr:openai")
            return httpx.Response(200, text="<svg>openai-js</svg>")
        if "models.dev/logos/openai.svg" in url:
            raise AssertionError("jsDelivr success must not probe Models.dev")
        if "providers/anthropic/logo.svg" in url:
            calls.append("jsdelivr:anthropic")
            return httpx.Response(404, text="not found")
        if "models.dev/logos/anthropic.svg" in url:
            calls.append("models_dev:anthropic")
            return httpx.Response(200, text="<svg>anthropic-default</svg>")
        if "providers/deepseek/logo.svg" in url:
            calls.append("jsdelivr:deepseek")
            return httpx.Response(200, text="<svg>deepseek-js</svg>")
        if "models.dev/logos/deepseek.svg" in url:
            raise AssertionError("each icon must use its own source decision")
        raise AssertionError(f"Unexpected URL {url}")

    service = CatalogIconProxyService(client=_FakeClient(responder))

    openai = await service.fetch_icon("openai")
    anthropic = await service.fetch_icon("anthropic")
    deepseek = await service.fetch_icon("deepseek")

    assert openai.source == "jsdelivr"
    assert anthropic.source == "models_dev"
    assert deepseek.source == "jsdelivr"
    assert calls == [
        "jsdelivr:openai",
        "jsdelivr:anthropic",
        "models_dev:anthropic",
        "jsdelivr:deepseek",
    ]


@pytest.mark.asyncio
async def test_unavailable_icon_sources_return_local_default_icon() -> None:
    calls: list[str] = []

    async def responder(url: str) -> httpx.Response:
        if "providers/chutes/logo.svg" in url:
            calls.append("jsdelivr")
            return httpx.Response(404, text="not found")
        if "models.dev/logos/chutes.svg" in url:
            calls.append("models_dev")
            raise httpx.ConnectTimeout("Models.dev is unreachable")
        raise AssertionError(f"Unexpected URL {url}")

    service = CatalogIconProxyService(client=_FakeClient(responder))

    result = await service.fetch_icon("chutes")

    assert result.source == "default"
    assert b'viewBox="0 0 24 24"' in result.content
    assert b'M9.8132 15.9038L9 18.75L8.1868 15.9038' in result.content
    assert calls == ["jsdelivr", "models_dev"]


@pytest.mark.asyncio
async def test_models_dev_failure_skips_later_fallback_requests() -> None:
    calls: list[str] = []

    async def responder(url: str) -> httpx.Response:
        if "providers/chutes/logo.svg" in url:
            calls.append("jsdelivr:chutes")
            return httpx.Response(404, text="not found")
        if "providers/clarifai/logo.svg" in url:
            calls.append("jsdelivr:clarifai")
            return httpx.Response(404, text="not found")
        if "models.dev/logos/chutes.svg" in url:
            calls.append("models_dev:chutes")
            raise httpx.ConnectTimeout("Models.dev is unreachable")
        if "models.dev/logos/clarifai.svg" in url:
            raise AssertionError("unavailable Models.dev source must be skipped")
        raise AssertionError(f"Unexpected URL {url}")

    service = CatalogIconProxyService(client=_FakeClient(responder))

    first = await service.fetch_icon("chutes")
    second = await service.fetch_icon("clarifai")

    assert first.source == "default"
    assert second.source == "default"
    assert calls == ["jsdelivr:chutes", "models_dev:chutes", "jsdelivr:clarifai"]


@pytest.mark.asyncio
async def test_404_falls_back_to_models_dev_without_affecting_other_icons() -> None:
    calls = {"anthropic": {"models": 0, "js": 0}, "deepseek": {"models": 0, "js": 0}}

    async def responder(url: str) -> httpx.Response:
        if "providers/openai/logo.svg" in url:
            return httpx.Response(200, text="<svg>openai-js</svg>")
        if "providers/anthropic/logo.svg" in url:
            calls["anthropic"]["js"] += 1
            return httpx.Response(404, text="not found")
        if "models.dev/logos/anthropic.svg" in url:
            calls["anthropic"]["models"] += 1
            return httpx.Response(200, text="<svg>anthropic-models</svg>")
        if "providers/deepseek/logo.svg" in url:
            calls["deepseek"]["js"] += 1
            return httpx.Response(200, text="<svg>deepseek-js</svg>")
        if "models.dev/logos/deepseek.svg" in url:
            calls["deepseek"]["models"] += 1
            return httpx.Response(200, text="<svg>deepseek-models</svg>")
        raise AssertionError(f"Unexpected URL {url}")

    service = CatalogIconProxyService(client=_FakeClient(responder))

    first = await service.fetch_icon("openai")
    second = await service.fetch_icon("anthropic")
    third = await service.fetch_icon("deepseek")

    assert first.source == "jsdelivr"
    assert second.source == "models_dev"
    assert third.source == "jsdelivr"
    assert calls == {
        "anthropic": {"models": 1, "js": 1},
        "deepseek": {"models": 0, "js": 1},
    }
