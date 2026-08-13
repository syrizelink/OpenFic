# -*- coding: utf-8 -*-
"""Models.dev-backed provider catalog with bundled snapshot fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.models.catalog.types import (
    CatalogMatch,
    CatalogProviderModelSummary,
    CatalogProviderModelsResponse,
    CatalogProviderSummary,
)
from app.models.registry import AdapterRegistry
from app.settings import BACKEND_DATA_DIR


@dataclass(frozen=True)
class _ProviderDefinition:
    provider_type: str
    models_dev_provider_id: str


_CATALOG_DIR = Path(__file__).resolve().parent
_BUNDLED_DIR = _CATALOG_DIR / "assets"
_CACHE_DIR = BACKEND_DATA_DIR / "model_provider_catalog"
_MODELS_DEV_API_URL = "https://models.dev/api.json"
_CATALOG_ICON_PATH_TEMPLATE = "/icons/model/catalog/{provider_id}.svg"
_SNAPSHOT_SCHEMA_VERSION = 4
_STATIC_PROVIDER_URLS: dict[str, str] = {
    "anthropic": "https://api.anthropic.com",
    "cerebras": "https://api.cerebras.ai/v1",
    "cohere": "https://api.cohere.com/v2",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "google-genai": "https://generativelanguage.googleapis.com",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openai": "https://api.openai.com/v1",
    "togetherai": "https://api.together.ai/v1",
    "v0": "https://api.v0.dev/v1",
    "venice": "https://api.venice.ai/api/v1",
    "vercel": "https://ai-gateway.vercel.sh/v1",
    "xai": "https://api.x.ai/v1",
}

_PROVIDER_DEFINITIONS: tuple[_ProviderDefinition, ...] = (
    _ProviderDefinition("openai", "openai"),
    _ProviderDefinition("anthropic", "anthropic"),
    _ProviderDefinition("google-genai", "google"),
    _ProviderDefinition("ollama", "ollama-cloud"),
    _ProviderDefinition("groq", "groq"),
    _ProviderDefinition("huggingface", "huggingface"),
    _ProviderDefinition("mistral", "mistral"),
    _ProviderDefinition("nvidia-ai-endpoints", "nvidia"),
    _ProviderDefinition("cohere", "cohere"),
    _ProviderDefinition("openrouter", "openrouter"),
    _ProviderDefinition("amazon-nova", "nova"),
    _ProviderDefinition("deepseek", "deepseek"),
)

_PROVIDER_BY_TYPE = {definition.provider_type: definition for definition in _PROVIDER_DEFINITIONS}
_PROVIDER_BY_MODELS_DEV_ID = {
    definition.models_dev_provider_id: definition for definition in _PROVIDER_DEFINITIONS
}
_REGISTERED_PROVIDER_TYPES = frozenset(AdapterRegistry.list_providers())
_EMBEDDING_FAMILIES = {
    "text-embedding",
    "mistral-embed",
    "cohere-embed",
    "titan-embed",
    "bge",
}

# 进程级 catalog snapshot 缓存：key 为 (快照文件路径, mtime)，避免每次请求重复解析大 JSON。
_SNAPSHOT_CACHE: dict[
    tuple[Path, int], tuple[dict[str, Any], str, str | None]
] = {}


class ModelProviderCatalogService:
    """Catalog access with bundled fallback and refreshable local cache."""

    def __init__(
        self,
        bundled_snapshot_path: Path | None = None,
        bundled_logo_dir: Path | None = None,
        cache_snapshot_path: Path | None = None,
        cache_metadata_path: Path | None = None,
        source_snapshot_path: Path | None = None,
        source_logo_dir: Path | None = None,
        served_icon_dir: Path | None = None,
    ) -> None:
        self.bundled_snapshot_path = bundled_snapshot_path or (
            _BUNDLED_DIR / "modelsdev-catalog.snapshot.json"
        )
        self.bundled_logo_dir = bundled_logo_dir or (_BUNDLED_DIR / "logos")
        self.cache_snapshot_path = cache_snapshot_path or (
            _CACHE_DIR / "modelsdev-catalog.cache.json"
        )
        self.cache_metadata_path = cache_metadata_path or (_CACHE_DIR / "metadata.json")
        self.source_snapshot_path = source_snapshot_path
        self.source_logo_dir = source_logo_dir
        self.served_icon_dir = served_icon_dir or (
            BACKEND_DATA_DIR / "icons" / "model" / "catalog"
        )

    async def list_providers(self) -> list[CatalogProviderSummary]:
        snapshot, _, _ = self._load_current_snapshot()
        providers = [
            self._provider_summary_from_payload(provider, resolve_static_url=True)
            for provider in snapshot.get("providers", [])
        ]
        return sorted(providers, key=lambda provider: provider.provider_type)

    async def get_provider(self, provider_type: str) -> CatalogProviderSummary:
        snapshot, _, _ = self._load_current_snapshot()
        provider = self._find_provider(snapshot, provider_type)
        if provider is None:
            raise KeyError(provider_type)
        return self._provider_summary_from_payload(provider, resolve_static_url=True)

    async def get_provider_models(
        self, provider_type: str, task_type: str
    ) -> CatalogProviderModelsResponse:
        provider = await self.get_provider(provider_type)
        snapshot, _, _ = self._load_current_snapshot()
        provider_payload = self._find_provider(snapshot, provider_type)
        if provider_payload is None:
            raise KeyError(provider_type)

        models = [
            CatalogProviderModelSummary.model_validate(model)
            for model in provider_payload.get("models", [])
            if model.get("task_type") == task_type
        ]
        models = self._sort_model_summaries_by_release_date(models)
        return CatalogProviderModelsResponse(
            provider=provider,
            task_type=task_type,
            models=models,
        )

    async def supports_reasoning(self, provider_type: str, model_id: str) -> bool:
        try:
            models = await self.get_provider_models(provider_type, "llm")
        except KeyError:
            return False
        return any(
            model.model_id == model_id
            and isinstance(model.metadata, dict)
            and model.metadata.get("reasoning") is True
            for model in models.models
        )

    async def supports_provider_model_reasoning(
        self, provider_type: str, url: str, model_id: str
    ) -> bool:
        catalog_match = await self.match_saved_provider(provider_type, url)
        if catalog_match is None:
            return False
        return await self.supports_reasoning(catalog_match.catalog_provider_type, model_id)

    async def refresh(self) -> None:
        try:
            raw_payload = await self._load_refresh_payload()
            normalized_snapshot = self._build_normalized_snapshot(
                raw_payload,
                {
                    **self._bundled_provider_urls(),
                    **_STATIC_PROVIDER_URLS,
                },
            )
            last_refreshed_at = datetime.now(UTC).isoformat()
            self._write_json_atomic(self.cache_snapshot_path, normalized_snapshot)
            self._write_json_atomic(
                self.cache_metadata_path,
                {"last_refreshed_at": last_refreshed_at},
            )
            logger.info(
                "Refreshed model provider catalog cache from Models.dev",
            )
        except Exception as exc:
            logger.warning("Catalog refresh failed, keeping last successful cache: {}", exc)

    async def match_saved_provider(
        self, provider_type: str, url: str
    ) -> CatalogMatch | None:
        providers = await self.list_providers()

        if provider_type != "openai-compatible":
            provider = next(
                (item for item in providers if item.provider_type == provider_type),
                None,
            )
            if provider is None:
                return None
            return CatalogMatch(
                catalog_provider_type=provider.provider_type,
                display_name=provider.display_name,
                default_url=provider.default_url,
                api=provider.api,
                icon_path=provider.icon_path,
                models_dev_provider_id=provider.models_dev_provider_id,
                matched_via="provider_type",
            )

        normalized_url = self.normalize_api_url(url)
        for provider in providers:
            if provider.api and self.normalize_api_url(provider.api) == normalized_url:
                return CatalogMatch(
                    catalog_provider_type=provider.provider_type,
                    display_name=provider.display_name,
                    default_url=provider.default_url,
                    api=provider.api,
                    icon_path=provider.icon_path,
                    models_dev_provider_id=provider.models_dev_provider_id,
                    matched_via="api",
                )
        return None

    def get_supported_task_types(
        self, provider_type: str, catalog_match: CatalogMatch | None = None
    ) -> list[str]:
        supported = set()
        if provider_type in _REGISTERED_PROVIDER_TYPES:
            supported.update(AdapterRegistry.get_supported_task_types(provider_type))
        if catalog_match is not None:
            try:
                provider = self._find_provider(
                    self._load_current_snapshot()[0], catalog_match.catalog_provider_type
                )
            except Exception:
                provider = None
            if provider is not None:
                counts = provider.get("model_counts", {})
                supported.update(
                    task_type
                    for task_type in ("llm", "embedding", "rerank")
                    if counts.get(task_type, 0) > 0
                )
        return sorted(supported)

    @staticmethod
    def normalize_api_url(url: str) -> str:
        return url.strip().lower().rstrip("/")

    def _load_current_snapshot(self) -> tuple[dict[str, Any], str, str | None]:
        cache_path = self.cache_snapshot_path
        if cache_path.exists():
            cache_mtime = cache_path.stat().st_mtime_ns
            cached = _SNAPSHOT_CACHE.get((cache_path, cache_mtime))
            if cached is not None:
                return cached
            try:
                snapshot = self._read_json(cache_path)
                if not self._is_current_snapshot(snapshot):
                    raise ValueError("Catalog cache schema is outdated")
                metadata = (
                    self._read_json(self.cache_metadata_path)
                    if self.cache_metadata_path.exists()
                    else {}
                )
                result = snapshot, "cache", metadata.get("last_refreshed_at")
                _SNAPSHOT_CACHE[(cache_path, cache_mtime)] = result
                return result
            except Exception as exc:
                logger.warning("Failed to load catalog cache, falling back to bundled: {}", exc)

        bundled_path = self.bundled_snapshot_path
        bundled_mtime = bundled_path.stat().st_mtime_ns
        cached = _SNAPSHOT_CACHE.get((bundled_path, bundled_mtime))
        if cached is not None:
            return cached
        snapshot = self._read_json(bundled_path)
        if not self._is_current_snapshot(snapshot):
            raise ValueError("Bundled catalog snapshot schema is outdated")
        result = snapshot, "bundled", None
        _SNAPSHOT_CACHE[(bundled_path, bundled_mtime)] = result
        return result

    def _find_provider(
        self, snapshot: dict[str, Any], provider_type: str
    ) -> dict[str, Any] | None:
        for provider in snapshot.get("providers", []):
            if provider.get("provider_type") == provider_type:
                return provider
        return None

    def _provider_summary_from_payload(
        self,
        provider_payload: dict[str, Any],
        resolve_static_url: bool = False,
    ) -> CatalogProviderSummary:
        counts = dict(provider_payload.get("model_counts") or {})
        provider_type = str(provider_payload.get("provider_type") or "")
        api_url = provider_payload.get("api") or provider_payload.get("default_url")
        if resolve_static_url and (not isinstance(api_url, str) or not api_url.strip()):
            api_url = _STATIC_PROVIDER_URLS.get(provider_type)
        models_dev_provider_id = provider_payload.get("models_dev_provider_id")
        return CatalogProviderSummary(
            provider_type=provider_type,
            display_name=str(provider_payload.get("display_name") or provider_type),
            default_url=api_url,
            api=api_url,
            icon_path=(
                self._icon_path_for(str(models_dev_provider_id))
                if models_dev_provider_id
                else provider_payload.get("icon_path")
            ),
            models_dev_provider_id=models_dev_provider_id,
            supported_task_types=self._supported_task_types_for(provider_type, counts),
            model_counts=counts,
        )

    def _build_normalized_snapshot(
        self,
        raw_payload: dict[str, Any],
        bundled_provider_urls: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        bundled_provider_urls = bundled_provider_urls or {}

        for raw_provider_key, raw_provider in sorted(raw_payload.items()):
            if not isinstance(raw_provider, dict):
                continue

            models_dev_provider_id = str(raw_provider.get("id") or raw_provider_key)
            definition = _PROVIDER_BY_MODELS_DEV_ID.get(models_dev_provider_id)
            provider_type = (
                definition.provider_type
                if definition is not None
                else models_dev_provider_id
            )
            display_name = str(raw_provider.get("name") or provider_type)
            api_url = raw_provider.get("api")
            if not isinstance(api_url, str) or not api_url.strip():
                api_url = bundled_provider_urls.get(provider_type)
            models_payload = raw_provider.get("models")
            if not isinstance(models_payload, dict):
                models_payload = {}

            normalized_models: list[dict[str, Any]] = []
            counts = {"llm": 0, "embedding": 0, "rerank": 0}
            for model_id, raw_model in models_payload.items():
                if not isinstance(raw_model, dict):
                    continue
                normalized_model = self._normalize_model(model_id, raw_model)
                normalized_models.append(normalized_model)
                counts[normalized_model["task_type"]] += 1

            provider_payload = {
                "provider_type": provider_type,
                "display_name": display_name,
                "default_url": api_url,
                "api": api_url,
                "icon_path": self._icon_path_for(models_dev_provider_id),
                "models_dev_provider_id": models_dev_provider_id,
                "supported_task_types": self._supported_task_types_for(
                    provider_type, counts
                ),
                "model_counts": counts,
                "models": self._sort_model_dicts_by_release_date(normalized_models),
            }
            providers.append(provider_payload)

        return {
            "schema_version": _SNAPSHOT_SCHEMA_VERSION,
            "providers": providers,
        }

    def _bundled_provider_urls(self) -> dict[str, str]:
        bundled_snapshot = self._read_json(self.bundled_snapshot_path)
        provider_urls: dict[str, str] = {}

        for provider in bundled_snapshot.get("providers", []):
            if not isinstance(provider, dict):
                continue
            provider_type = provider.get("provider_type")
            api_url = provider.get("api") or provider.get("default_url")
            if isinstance(provider_type, str) and isinstance(api_url, str) and api_url.strip():
                provider_urls[provider_type] = api_url

        return provider_urls

    def _normalize_model(self, model_id: str, raw_model: dict[str, Any]) -> dict[str, Any]:
        display_name = str(raw_model.get("name") or model_id)
        family = str(raw_model.get("family") or "")
        task_type = self._classify_model(display_name, family)

        metadata: dict[str, Any] | None = {
            "release_date": raw_model.get("release_date"),
            "reasoning": raw_model.get("reasoning"),
            "tool_call": raw_model.get("tool_call"),
            "modalities": raw_model.get("modalities"),
            "limit": raw_model.get("limit"),
            "cost": raw_model.get("cost"),
        }

        if metadata is not None and not any(value is not None for value in metadata.values()):
            metadata = None

        return {
            "model_id": model_id,
            "display_name": display_name,
            "task_type": task_type,
            "metadata": metadata,
        }

    def _classify_model(self, name: str, family: str) -> str:
        lowered_name = name.lower()
        lowered_family = family.lower()

        if (
            ("embed" in lowered_name or "embedding" in lowered_name)
            and lowered_family in _EMBEDDING_FAMILIES
        ):
            return "embedding"
        if "rerank" in lowered_name:
            return "rerank"
        return "llm"

    def _supported_task_types_for(
        self, provider_type: str, counts: dict[str, int]
    ) -> list[str]:
        supported = set()
        if provider_type in _REGISTERED_PROVIDER_TYPES:
            supported.update(AdapterRegistry.get_supported_task_types(provider_type))
        supported.update(
            task_type
            for task_type in ("llm", "embedding", "rerank")
            if counts.get(task_type, 0) > 0
        )
        return sorted(supported)

    @staticmethod
    def _release_date_sort_key(
        value: str | None, index: int
    ) -> tuple[int, int, int, int, int]:
        if not value:
            return (1, 0, 0, 0, index)

        try:
            parts = [int(part) for part in str(value).split("-")]
        except ValueError:
            return (1, 0, 0, 0, index)

        if len(parts) == 3:
            year, month, day = parts
            if month < 1 or month > 12 or day < 1 or day > 31:
                return (1, 0, 0, 0, index)
        elif len(parts) == 2:
            year, month = parts
            day = 0
            if month < 1 or month > 12:
                return (1, 0, 0, 0, index)
        elif len(parts) == 1:
            year = parts[0]
            month = 0
            day = 0
        else:
            return (1, 0, 0, 0, index)

        return (0, -year, -month, -day, index)

    def _sort_model_dicts_by_release_date(
        self, models: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        decorated = [
            (
                self._release_date_sort_key(
                    ((model.get("metadata") or {}).get("release_date")),
                    index,
                ),
                model,
            )
            for index, model in enumerate(models)
        ]
        decorated.sort(key=lambda item: item[0])
        return [model for _, model in decorated]

    def _sort_model_summaries_by_release_date(
        self, models: list[CatalogProviderModelSummary]
    ) -> list[CatalogProviderModelSummary]:
        decorated = [
            (
                self._release_date_sort_key(
                    (model.metadata or {}).get("release_date"),
                    index,
                ),
                model,
            )
            for index, model in enumerate(models)
        ]
        decorated.sort(key=lambda item: item[0])
        return [model for _, model in decorated]

    async def _load_refresh_payload(self) -> dict[str, Any]:
        if self.source_snapshot_path is not None and self.source_snapshot_path.exists():
            return self._read_json(self.source_snapshot_path)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_MODELS_DEV_API_URL)
            response.raise_for_status()
            return response.json()

    def _icon_path_for(self, provider_id: str) -> str:
        return _CATALOG_ICON_PATH_TEMPLATE.format(provider_id=provider_id)

    def _is_current_snapshot(self, snapshot: dict[str, Any]) -> bool:
        return (
            snapshot.get("schema_version") == _SNAPSHOT_SCHEMA_VERSION
            and isinstance(snapshot.get("providers"), list)
        )

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        temp_path.replace(path)
