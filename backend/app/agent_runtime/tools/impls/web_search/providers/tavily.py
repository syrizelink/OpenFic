"""Provider Tavily API (SDK resmi)."""

from __future__ import annotations

import httpx
from tavily import AsyncTavilyClient

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
)


class TavilyProvider(WebSearchProvider):
    name = "tavily"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("API Key Tavily belum dikonfigurasi")

        http_client = (
            httpx.AsyncClient(trust_env=False)
            if not config.trust_proxy_environment
            else None
        )
        if http_client is None:
            client = AsyncTavilyClient(api_key=config.api_key)
        else:
            client = AsyncTavilyClient(api_key=config.api_key, client=http_client)
        try:
            try:
                payload = await client.search(
                    query=query,
                    max_results=config.max_results,
                    search_depth="basic",
                    include_answer=True,
                )
            except Exception as exc:
                raise ToolExecutionError(f"Pencarian Tavily gagal: {exc}") from exc
        finally:
            await client.close()
            if http_client is not None:
                await http_client.aclose()

        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=item.get("content") or "",
            )
            for item in payload.get("results") or []
            if isinstance(item, dict)
        ]
        answer = payload.get("answer")
        return WebSearchResponse(
            answer=answer if isinstance(answer, str) and answer else None,
            results=results,
        )
