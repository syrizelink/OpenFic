# -*- coding: utf-8 -*-
"""
Model provider catalog API tests.
"""

from typing import Any

import pytest
from httpx import AsyncClient


def _release_sort_tuple(value: str | None) -> tuple[int, int, int, int]:
    if not value:
        return (1, 0, 0, 0)

    parts = value.split("-")
    if len(parts) == 3:
        year, month, day = (int(part) for part in parts)
    elif len(parts) == 2:
        year, month = (int(part) for part in parts)
        day = 0
    else:
        return (1, 0, 0, 0)

    return (0, -year, -month, -day)


@pytest.mark.asyncio
async def test_catalog_status_and_provider_listing_endpoints(client: AsyncClient) -> None:
    status_response = await client.get("/api/v1/model-provider-catalog/status")
    providers_response = await client.get("/api/v1/model-provider-catalog/providers")

    assert status_response.status_code == 200
    assert providers_response.status_code == 200

    status_payload = status_response.json()
    providers_payload = providers_response.json()

    assert status_payload["source"] in {"bundled", "cache"}
    assert status_payload["provider_count"] >= 1
    assert status_payload["model_count"] >= 1
    assert providers_payload[0].keys() >= {
        "provider_type",
        "display_name",
        "default_url",
        "api",
        "icon_path",
        "models_dev_provider_id",
        "supported_task_types",
        "model_counts",
    }
    assert providers_payload[0]["icon_path"].startswith("/icons/model/catalog/")


@pytest.mark.asyncio
async def test_catalog_provider_models_endpoint_filters_by_task_type(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/model-provider-catalog/providers/openai/models",
        params={"task_type": "embedding"},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["provider"]["provider_type"] == "openai"
    assert payload["task_type"] == "embedding"
    assert all(model["task_type"] == "embedding" for model in payload["models"])
    assert payload["models"][0]["metadata"]["limit"]["context"] is not None
    assert "input" in payload["models"][0]["metadata"]["cost"]
    assert payload["models"][0]["metadata"]["modalities"]["input"]


@pytest.mark.asyncio
async def test_catalog_provider_models_endpoint_returns_release_date_desc_order(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/model-provider-catalog/providers/openai/models",
        params={"task_type": "llm"},
    )

    assert response.status_code == 200

    payload = response.json()
    models: list[dict[str, Any]] = payload["models"]
    release_dates = [
        (model.get("metadata") or {}).get("release_date") for model in models
    ]

    assert sum(value is not None for value in release_dates) >= 2
    assert release_dates == sorted(release_dates, key=_release_sort_tuple)
    assert models[0]["metadata"]["release_date"] is not None


@pytest.mark.asyncio
async def test_catalog_refresh_endpoint_returns_updated_status(client: AsyncClient) -> None:
    response = await client.post("/api/v1/model-provider-catalog/refresh")

    assert response.status_code == 200

    payload = response.json()
    assert payload["source"] == "cache"
    assert payload["last_refreshed_at"] is not None
