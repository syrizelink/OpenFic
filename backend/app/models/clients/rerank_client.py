# -*- coding: utf-8 -*-
"""
Rerank Client - klien pemanggilan model rerank.
"""

import math
from dataclasses import dataclass
from typing import Any

import asyncio

import httpx
from loguru import logger

from app.core.errors import (
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    ValidationError,
)
from app.models.clients.client_factory import ClientFactory
from app.models.helpers.openrouter_attribution import get_openrouter_attribution_headers


DEFAULT_RERANK_TIMEOUT = 60
SUPPORTED_RERANK_PROVIDERS = {
    "openrouter",
    "openai-compatible",
    "openai",
    "nvidia-ai-endpoints",
    "builtin",
}


@dataclass
class RerankConfig:
    """Konfigurasi pemanggilan rerank."""

    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    custom_headers: dict[str, str] | None = None
    request_timeout: int = DEFAULT_RERANK_TIMEOUT
    use_openai_compatible: bool = True


@dataclass
class RerankItem:
    """Satu hasil rerank."""

    index: int
    relevance_score: float


@dataclass
class RerankResponse:
    """Respons rerank."""

    results: list[RerankItem]
    model: str | None = None
    usage: dict[str, Any] | None = None


class RerankClient:
    """Klien rerank, memakai antarmuka HTTP bergaya OpenAI-compatible."""

    def __init__(self, config: RerankConfig):
        self.runtime_provider_type = (
            "builtin"
            if config.provider_type == "builtin"
            else "openai-compatible"
            if config.use_openai_compatible
            else config.provider_type
        )
        if self.runtime_provider_type not in SUPPORTED_RERANK_PROVIDERS:
            raise ValueError(
                f"Unsupported rerank provider_type: {self.runtime_provider_type}"
            )
        self.config = config

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> RerankResponse:
        if self.runtime_provider_type == "builtin":
            return await self._rerank_builtin(query, documents, top_n)

        payload: dict[str, Any] = {
            "model": self.config.model_id,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        try:
            async with ClientFactory.create_client(
                timeout=float(self.config.request_timeout)
            ) as client:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                }
                if self.config.provider_type == "openrouter":
                    headers.update(get_openrouter_attribution_headers())
                headers.update(self.config.custom_headers or {})
                response = await client.post(
                    f"{self.config.base_url.rstrip('/')}/rerank",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Rerank request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Rerank request failed: {exc}") from exc

        if response.status_code == 401:
            raise ProviderAuthError("Rerank authentication failed")
        if response.status_code == 429:
            raise RateLimitError("Rerank rate limit exceeded")
        if response.status_code >= 400:
            raise ProviderError(
                f"Rerank request failed with status {response.status_code}"
            )

        data = response.json()
        results_raw = data.get("results")
        if not isinstance(results_raw, list):
            raise ValidationError("Rerank response missing results")

        parsed_results: list[RerankItem] = []
        for item in results_raw:
            if not isinstance(item, dict):
                raise ValidationError("Invalid rerank result item")
            index = item.get("index")
            score = item.get("relevance_score")
            if not isinstance(index, int) or not isinstance(score, (int, float)):
                raise ValidationError("Rerank result missing index or relevance_score")
            if index < 0 or index >= len(documents):
                raise ValidationError("Rerank result index out of range")
            parsed_results.append(
                RerankItem(index=index, relevance_score=float(score))
            )

        logger.debug("Rerank request succeeded with {} results", len(parsed_results))
        return RerankResponse(
            results=parsed_results,
            model=data.get("model"),
            usage=data.get("usage"),
        )

    async def _rerank_builtin(
        self, query: str, documents: list[str], top_n: int | None
    ) -> RerankResponse:
        """Menghitung skor relevansi memakai model rerank lokal fastembed."""
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
        except ModuleNotFoundError as exc:
            raise ImportError(
                "fastembed belum terpasang. Jalankan uv sync untuk memasang dependensi."
            ) from exc

        from app.models.clients.fastembed_embeddings import _load_fastembed_model

        def _compute() -> RerankResponse:
            encoder = _load_fastembed_model(TextCrossEncoder, self.config.model_id)
            scores = list(encoder.rerank(query, documents))
            items = [
                RerankItem(
                    index=i,
                    relevance_score=1.0 / (1.0 + math.exp(-float(score))),
                )
                for i, score in enumerate(scores)
            ]
            if top_n is not None:
                items = sorted(items, key=lambda it: it.relevance_score, reverse=True)[:top_n]
            return RerankResponse(results=items, model=self.config.model_id)

        return await asyncio.to_thread(_compute)
