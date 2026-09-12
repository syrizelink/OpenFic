"""Provider Zhipu Web Search API (SDK resmi)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from zai import ZhipuAiClient

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
)

DEFAULT_ZHIPU_SEARCH_ENGINE = "search_pro"


def _run_sync_search(api_key: str, query: str, config: WebSearchProviderConfig) -> Any:
    http_client = httpx.Client(trust_env=False) if not config.trust_proxy_environment else None
    if http_client is None:
        client = ZhipuAiClient(api_key=api_key)
    else:
        client = ZhipuAiClient(api_key=api_key, http_client=http_client)
    try:
        return client.web_search.web_search(
            search_engine=config.extra(
                "zhipu_search_engine", DEFAULT_ZHIPU_SEARCH_ENGINE
            ),
            search_query=query,
            search_intent=False,
            count=config.max_results,
            content_size="medium",
        )
    finally:
        client.close()
        if http_client is not None:
            http_client.close()


class ZhipuProvider(WebSearchProvider):
    name = "zhipu"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("API Key Zhipu belum dikonfigurasi")

        try:
            response = await asyncio.to_thread(
                _run_sync_search, config.api_key, query, config
            )
        except Exception as exc:
            raise ToolExecutionError(f"Pencarian Zhipu gagal: {exc}") from exc

        results = [
            WebSearchResult(
                title=item.title or "",
                url=item.link or "",
                snippet=item.content or "",
            )
            for item in response.search_result or []
        ]
        return WebSearchResponse(results=results)
