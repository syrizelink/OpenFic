# -*- coding: utf-8 -*-
"""
Catalog model icon API tests.
"""

import httpx
import pytest
import respx
from httpx import AsyncClient


@pytest.mark.asyncio
@respx.mock
async def test_catalog_icon_route_prefers_jsdelivr_without_probing_models_dev(
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
    response = await client.get("/icons/model/catalog/openai.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text == "<svg>jsdelivr</svg>"
    assert jsdelivr_route.called


@pytest.mark.asyncio
@respx.mock
async def test_catalog_icon_route_falls_back_per_icon_without_changing_jsdelivr_priority(
    client: AsyncClient,
) -> None:
    jsdelivr_calls = {"openai": 0, "anthropic": 0, "deepseek": 0}
    modelsdev_calls = {"anthropic": 0}

    async def jsdelivr_openai(request: httpx.Request) -> httpx.Response:
        jsdelivr_calls["openai"] += 1
        return httpx.Response(
            200,
            text="<svg>jsdelivr-openai</svg>",
            headers={"content-type": "image/svg+xml"},
            request=request,
        )

    async def jsdelivr_anthropic(request: httpx.Request) -> httpx.Response:
        jsdelivr_calls["anthropic"] += 1
        return httpx.Response(
            404,
            text="not found",
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
    assert third.text == "<svg>jsdelivr-deepseek</svg>"
    assert jsdelivr_calls == {"openai": 1, "anthropic": 1, "deepseek": 1}
    assert modelsdev_calls == {"anthropic": 1}
