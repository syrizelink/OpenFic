# -*- coding: utf-8 -*-
"""
Model provider catalog service tests.
"""

import json
from pathlib import Path

import pytest

from app.models.catalog.service import ModelProviderCatalogService

_OPENAI_ICON_URL = "/icons/model/catalog/openai.svg"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sample_modelsdev_payload() -> dict[str, object]:
    return {
        "openai": {
            "id": "openai",
            "name": "OpenAI",
            "api": "https://api.openai.com/v1",
            "models": {
                "gpt-4.1": {
                    "id": "gpt-4.1",
                    "name": "gpt-4.1",
                    "family": "gpt-4.1",
                    "release_date": "2025-04-14",
                    "reasoning": True,
                    "tool_call": True,
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "limit": {"context": 1048576, "output": 32768},
                    "cost": {"input": 2.0, "output": 8.0},
                },
                "gpt-4o-mini": {
                    "id": "gpt-4o-mini",
                    "name": "gpt-4o-mini",
                    "family": "gpt-4o",
                    "release_date": "2024-07-18",
                    "reasoning": False,
                    "tool_call": True,
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "limit": {"context": 128000, "output": 16384},
                    "cost": {"input": 0.15, "output": 0.6},
                },
                "text-embedding-3-small": {
                    "id": "text-embedding-3-small",
                    "name": "text-embedding-3-small",
                    "family": "text-embedding",
                    "release_date": "2024-01-25",
                    "reasoning": False,
                    "tool_call": False,
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "limit": {"context": 8191, "output": 1536},
                    "cost": {"input": 0.02, "output": 0},
                },
            },
        },
        "nvidia": {
            "id": "nvidia",
            "name": "Nvidia",
            "api": "https://integrate.api.nvidia.com/v1",
            "models": {
                "nvidia/rerank-qa-mistral-4b": {
                    "id": "nvidia/rerank-qa-mistral-4b",
                    "name": "nvidia/rerank-qa-mistral-4b",
                    "family": "mistral",
                    "release_date": "2024-08-01",
                    "reasoning": False,
                    "tool_call": False,
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "limit": {"context": 32000, "output": 1024},
                    "cost": {"input": 1.1, "output": 0},
                },
                "baai/bge-m3": {
                    "id": "baai/bge-m3",
                    "name": "baai/bge-m3",
                    "family": "bge",
                    "release_date": "2024-05-10",
                    "reasoning": False,
                    "tool_call": False,
                },
            },
        },
        "openrouter": {
            "id": "openrouter",
            "name": "OpenRouter",
            "api": "https://openrouter.ai/api/v1",
            "models": {
                "openai/gpt-4.1": {
                    "id": "openai/gpt-4.1",
                    "name": "openai/gpt-4.1",
                    "family": "gpt-4.1",
                    "release_date": "2025-04-14",
                    "reasoning": True,
                    "tool_call": True,
                }
            },
        },
        "upstage": {
            "id": "upstage",
            "name": "Upstage",
            "api": "https://api.upstage.ai/v1/solar",
            "models": {
                "solar-mini": {
                    "id": "solar-mini",
                    "name": "solar-mini",
                    "family": "solar-mini",
                    "release_date": "2024-06-12",
                    "reasoning": False,
                    "tool_call": True,
                },
                "solar-pro2": {
                    "id": "solar-pro2",
                    "name": "solar-pro2",
                    "family": "solar-pro",
                    "release_date": "2025-05-20",
                    "reasoning": True,
                    "tool_call": True,
                },
                "solar-pro3": {
                    "id": "solar-pro3",
                    "name": "solar-pro3",
                    "family": "solar-pro",
                    "release_date": "2026-01",
                    "reasoning": True,
                    "tool_call": True,
                }
            },
        },
    }


def _build_service(tmp_path: Path) -> ModelProviderCatalogService:
    bundled_snapshot_path = tmp_path / "bundled" / "snapshot.json"
    cache_snapshot_path = tmp_path / "cache" / "snapshot.json"
    cache_metadata_path = tmp_path / "cache" / "metadata.json"
    source_snapshot_path = tmp_path / "source" / "modelsdev-api.json"
    bundled_logo_dir = tmp_path / "bundled" / "logos"
    source_logo_dir = tmp_path / "source-logos"
    served_icon_dir = tmp_path / "served-icons"

    raw_payload = _sample_modelsdev_payload()
    bootstrap_service = ModelProviderCatalogService(
        bundled_snapshot_path=bundled_snapshot_path,
        bundled_logo_dir=bundled_logo_dir,
        cache_snapshot_path=cache_snapshot_path,
        cache_metadata_path=cache_metadata_path,
        source_snapshot_path=source_snapshot_path,
        source_logo_dir=source_logo_dir,
        served_icon_dir=served_icon_dir,
    )
    _write_json(
        bundled_snapshot_path,
        bootstrap_service._build_normalized_snapshot(raw_payload),
    )
    _write_json(source_snapshot_path, raw_payload)

    for provider_id in ["openai", "nvidia", "openrouter", "upstage"]:
        (bundled_logo_dir / provider_id).mkdir(parents=True, exist_ok=True)
        (bundled_logo_dir / provider_id / "logo.svg").write_text(
            f"<svg>{provider_id}</svg>", encoding="utf-8"
        )
        (source_logo_dir / provider_id).mkdir(parents=True, exist_ok=True)
        (source_logo_dir / provider_id / "logo.svg").write_text(
            f"<svg>{provider_id}-source</svg>", encoding="utf-8"
        )

    return bootstrap_service


@pytest.mark.asyncio
async def test_catalog_service_uses_bundled_snapshot_until_refresh(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    providers = await service.list_providers()

    assert [provider.provider_type for provider in providers] == [
        "nvidia-ai-endpoints",
        "openai",
        "openrouter",
        "upstage",
    ]
    assert providers[1].icon_path == _OPENAI_ICON_URL


@pytest.mark.asyncio
async def test_catalog_service_refreshes_cache_and_keeps_last_successful_cache_on_failure(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    await service.refresh()
    assert service.cache_snapshot_path.exists()
    refreshed_metadata = json.loads(service.cache_metadata_path.read_text(encoding="utf-8"))
    assert refreshed_metadata["last_refreshed_at"]

    providers = await service.list_providers()
    assert providers[0].supported_task_types == ["embedding", "llm", "rerank"]

    assert service.source_snapshot_path is not None
    service.source_snapshot_path.write_text("{", encoding="utf-8")
    await service.refresh()
    preserved_metadata = json.loads(service.cache_metadata_path.read_text(encoding="utf-8"))
    assert preserved_metadata == refreshed_metadata

    openai_provider = await service.get_provider("openai")
    assert openai_provider.default_url == "https://api.openai.com/v1"
    assert openai_provider.model_counts == {"llm": 2, "embedding": 1, "rerank": 0}


@pytest.mark.asyncio
async def test_catalog_service_applies_locked_model_classification_and_display_metadata(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    openai_models = await service.get_provider_models("openai", "llm")
    embedding_models = await service.get_provider_models("openai", "embedding")
    rerank_models = await service.get_provider_models(
        "nvidia-ai-endpoints", "rerank"
    )

    assert [model.model_id for model in openai_models.models] == ["gpt-4.1", "gpt-4o-mini"]
    assert openai_models.models[0].metadata == {
        "release_date": "2025-04-14",
        "reasoning": True,
        "tool_call": True,
        "modalities": {"input": ["text"], "output": ["text"]},
        "limit": {"context": 1048576, "output": 32768},
        "cost": {"input": 2.0, "output": 8.0},
    }

    assert [model.model_id for model in embedding_models.models] == [
        "text-embedding-3-small"
    ]
    assert embedding_models.models[0].metadata == {
        "release_date": "2024-01-25",
        "reasoning": False,
        "tool_call": False,
        "modalities": {"input": ["text"], "output": ["text"]},
        "limit": {"context": 8191, "output": 1536},
        "cost": {"input": 0.02, "output": 0},
    }

    assert [model.model_id for model in rerank_models.models] == [
        "nvidia/rerank-qa-mistral-4b"
    ]
    assert rerank_models.models[0].metadata == {
        "release_date": "2024-08-01",
        "reasoning": False,
        "tool_call": False,
        "modalities": {"input": ["text"], "output": ["text"]},
        "limit": {"context": 32000, "output": 1024},
        "cost": {"input": 1.1, "output": 0},
    }


@pytest.mark.asyncio
async def test_catalog_service_matches_openai_compatible_provider_by_exact_api(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    match = await service.match_saved_provider(
        "openai-compatible",
        "https://api.upstage.ai/v1/solar/",
    )
    assert match is not None
    assert match.catalog_provider_type == "upstage"
    assert match.display_name == "Upstage"

    models = await service.get_provider_models("upstage", "llm")
    assert [model.model_id for model in models.models] == [
        "solar-pro3",
        "solar-pro2",
        "solar-mini",
    ]
