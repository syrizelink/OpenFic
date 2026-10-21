"""Local Infistar catalog entries survive existing caches and Models.dev refreshes."""

import json
from pathlib import Path

import pytest

from app.models.catalog.service import ModelProviderCatalogService


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["bundled", "cache"])
async def test_infistar_is_available_without_modelsdev_entry(
    tmp_path: Path, source: str
) -> None:
    bundled = tmp_path / "bundled.json"
    cache = tmp_path / "cache.json"
    snapshot = {"schema_version": 4, "providers": []}
    if source == "cache":
        # An older cache may already contain the local provider without its icon.
        snapshot["providers"] = [
            {
                "provider_type": "infistar",
                "display_name": "Infistar",
                "api": "https://infistar.cc/v1",
                "icon_path": None,
                "models_dev_provider_id": None,
                "models": [],
                "model_counts": {"llm": 0, "embedding": 0, "rerank": 0},
            }
        ]
    bundled.write_text(json.dumps(snapshot), encoding="utf-8")
    if source == "cache":
        cache.write_text(json.dumps(snapshot), encoding="utf-8")
    service = ModelProviderCatalogService(
        bundled_snapshot_path=bundled,
        cache_snapshot_path=cache,
        cache_metadata_path=tmp_path / "metadata.json",
        source_snapshot_path=tmp_path / "source.json",
    )

    provider = await service.get_provider("infistar")
    assert provider.display_name == "Infistar"
    assert provider.api == provider.default_url == "https://infistar.cc/v1"
    assert provider.supported_task_types == ["embedding", "llm", "rerank"]
    assert provider.models_dev_provider_id is None
    assert provider.icon_path == "/icons/model/catalog/infistar.svg"
    assert provider.model_counts == {"llm": 0, "embedding": 0, "rerank": 0}
    for provider_type in ["infistar", "openai-compatible"]:
        match = await service.match_saved_provider(
            provider_type, "https://infistar.cc/v1/"
        )
        assert match is not None
        assert match.catalog_provider_type == "infistar"
        assert service.get_supported_task_types(provider_type, match) == [
            "embedding",
            "llm",
            "rerank",
        ]

    assert service.source_snapshot_path is not None
    service.source_snapshot_path.write_text("{}", encoding="utf-8")
    await service.refresh()
    assert (await service.get_provider("infistar")) == provider
    for task_type in provider.supported_task_types:
        assert (await service.get_provider_models("infistar", task_type)).models == []

    # If Models.dev adds Infistar later, retain its actual model metadata once only.
    service.source_snapshot_path.write_text(
        json.dumps(
            {
                "infistar": {
                    "id": "infistar",
                    "name": "Infistar",
                    "api": "https://infistar.cc/v1",
                    "models": {"qwen-plus": {"name": "Qwen Plus"}},
                }
            }
        ),
        encoding="utf-8",
    )
    await service.refresh()
    providers = await service.list_providers()
    assert sum(item.provider_type == "infistar" for item in providers) == 1
    models = await service.get_provider_models("infistar", "llm")
    assert [model.model_id for model in models.models] == ["qwen-plus"]
