# -*- coding: utf-8 -*-
"""
Rerank Client - Rerank 模型调用客户端。
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
    """Rerank 调用配置。"""

    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    request_timeout: int = DEFAULT_RERANK_TIMEOUT
    use_openai_compatible: bool = True


@dataclass
class RerankItem:
    """单条 Rerank 结果。"""

    index: int
    relevance_score: float


@dataclass
class RerankResponse:
    """Rerank 响应。"""

    results: list[RerankItem]
    model: str | None = None
    usage: dict[str, Any] | None = None


class RerankClient:
    """Rerank 客户端，使用 OpenAI-compatible 风格 HTTP 接口。"""

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
                response = await client.post(
                    f"{self.config.base_url.rstrip('/')}/rerank",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
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
        """使用 fastembed 本地重排模型计算相关性分数。"""
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
        except ModuleNotFoundError as exc:
            raise ImportError(
                "fastembed 未安装。请运行 uv sync 安装依赖。"
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
