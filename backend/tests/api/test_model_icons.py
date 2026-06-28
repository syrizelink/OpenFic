# -*- coding: utf-8 -*-
"""
Catalog model icon API tests.
"""

import asyncio

import httpx
import pytest
import respx
from httpx import AsyncClient


@pytest.mark.asyncio
@respx.mock
async def test_catalog_icon_route_proxies_svg_with_backend_entrypoint(
    client: AsyncClient,
) -> None:
    jsdelivr_route = respx.get(
        "https://cdn.jsdelivr.net/gh/sst/models.dev@dev/providers/openai/logo.svg"
    ).mock(
        side_effect=lambda request: httpx.Response(
            200,
            text="<svg>jsdelivr</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )
    )
    modelsdev_route = respx.get("https://models.dev/logos/openai.svg").mock(
        side_effect=lambda request: httpx.Response(
            200,
            text="<svg>modelsdev</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )
    )

    response = await client.get("/icons/model/catalog/openai.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text in {"<svg>jsdelivr</svg>", "<svg>modelsdev</svg>"}
    assert jsdelivr_route.called
    assert modelsdev_route.called


@pytest.mark.asyncio
@respx.mock
async def test_catalog_icon_route_fails_over_and_switches_cached_source(
    client: AsyncClient,
) -> None:
    jsdelivr_calls = {"openai": 0, "anthropic": 0, "deepseek": 0}
    modelsdev_calls = {"openai": 0, "anthropic": 0, "deepseek": 0}

    async def jsdelivr_openai(request: httpx.Request) -> httpx.Response:
        jsdelivr_calls["openai"] += 1
        return httpx.Response(
            200,
            text="<svg>jsdelivr-openai</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )

    async def modelsdev_openai(request: httpx.Request) -> httpx.Response:
        modelsdev_calls["openai"] += 1
        await asyncio.sleep(0.02)
        return httpx.Response(
            200,
            text="<svg>modelsdev-openai</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )

    async def jsdelivr_anthropic(request: httpx.Request) -> httpx.Response:
        jsdelivr_calls["anthropic"] += 1
        return httpx.Response(
            503,
            text="upstream error",
            headers={"content-type": "text/plain"},
            request=request,
        )

    async def modelsdev_anthropic(request: httpx.Request) -> httpx.Response:
        modelsdev_calls["anthropic"] += 1
        return httpx.Response(
            200,
            text="<svg>modelsdev-anthropic</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )

    async def jsdelivr_deepseek(request: httpx.Request) -> httpx.Response:
        jsdelivr_calls["deepseek"] += 1
        return httpx.Response(
            200,
            text="<svg>jsdelivr-deepseek</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )

    async def modelsdev_deepseek(request: httpx.Request) -> httpx.Response:
        modelsdev_calls["deepseek"] += 1
        return httpx.Response(
            200,
            text="<svg>modelsdev-deepseek</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )

    respx.get(
        "https://cdn.jsdelivr.net/gh/sst/models.dev@dev/providers/openai/logo.svg"
    ).mock(side_effect=jsdelivr_openai)
    respx.get("https://models.dev/logos/openai.svg").mock(side_effect=modelsdev_openai)
    respx.get(
        "https://cdn.jsdelivr.net/gh/sst/models.dev@dev/providers/anthropic/logo.svg"
    ).mock(side_effect=jsdelivr_anthropic)
    respx.get("https://models.dev/logos/anthropic.svg").mock(
        side_effect=modelsdev_anthropic
    )
    respx.get(
        "https://cdn.jsdelivr.net/gh/sst/models.dev@dev/providers/deepseek/logo.svg"
    ).mock(side_effect=jsdelivr_deepseek)
    respx.get("https://models.dev/logos/deepseek.svg").mock(
        side_effect=modelsdev_deepseek
    )

    first = await client.get("/icons/model/catalog/openai.svg")
    second = await client.get("/icons/model/catalog/anthropic.svg")
    third = await client.get("/icons/model/catalog/deepseek.svg")

    assert first.status_code == 200
    assert first.text == "<svg>jsdelivr-openai</svg>"
    assert second.status_code == 200
    assert second.text == "<svg>modelsdev-anthropic</svg>"
    assert third.status_code == 200
    assert third.text == "<svg>modelsdev-deepseek</svg>"
    assert jsdelivr_calls == {"openai": 1, "anthropic": 1, "deepseek": 0}
    assert modelsdev_calls == {"openai": 1, "anthropic": 1, "deepseek": 1}
