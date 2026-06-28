# -*- coding: utf-8 -*-
"""
Catalog icon proxy service tests.
"""

import asyncio

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
async def test_concurrent_first_requests_share_single_probe() -> None:
    service = CatalogIconProxyService()
    calls = {"openai": {"models": 0, "js": 0}, "anthropic": {"models": 0, "js": 0}}

    async def responder(url: str) -> httpx.Response:
        if "providers/openai/logo.svg" in url:
            calls["openai"]["js"] += 1
            return httpx.Response(200, text="<svg>openai-js</svg>")
        if "models.dev/logos/openai.svg" in url:
            calls["openai"]["models"] += 1
            await asyncio.sleep(0.02)
            return httpx.Response(200, text="<svg>openai-models</svg>")
        if "providers/anthropic/logo.svg" in url:
            calls["anthropic"]["js"] += 1
            return httpx.Response(200, text="<svg>anthropic-js</svg>")
        if "models.dev/logos/anthropic.svg" in url:
            calls["anthropic"]["models"] += 1
            return httpx.Response(200, text="<svg>anthropic-models</svg>")
        raise AssertionError(f"Unexpected URL {url}")

    service._client = _FakeClient(responder)  # type: ignore[assignment]

    first, second = await asyncio.gather(
        service.fetch_icon("openai"),
        service.fetch_icon("anthropic"),
    )

    assert first.source == "jsdelivr"
    assert second.source == "jsdelivr"
    assert service.winner == "jsdelivr"
    assert calls == {
        "openai": {"models": 1, "js": 1},
        "anthropic": {"models": 0, "js": 1},
    }


@pytest.mark.asyncio
async def test_404_falls_back_without_switching_global_winner() -> None:
    service = CatalogIconProxyService()
    calls = {"anthropic": {"models": 0, "js": 0}, "deepseek": {"models": 0, "js": 0}}

    async def responder(url: str) -> httpx.Response:
        if "providers/openai/logo.svg" in url:
            return httpx.Response(200, text="<svg>openai-js</svg>")
        if "models.dev/logos/openai.svg" in url:
            await asyncio.sleep(0.02)
            return httpx.Response(200, text="<svg>openai-models</svg>")
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

    service._client = _FakeClient(responder)  # type: ignore[assignment]

    first = await service.fetch_icon("openai")
    second = await service.fetch_icon("anthropic")
    third = await service.fetch_icon("deepseek")

    assert first.source == "jsdelivr"
    assert second.source == "models_dev"
    assert third.source == "jsdelivr"
    assert service.winner == "jsdelivr"
    assert calls == {
        "anthropic": {"models": 1, "js": 1},
        "deepseek": {"models": 0, "js": 1},
    }
