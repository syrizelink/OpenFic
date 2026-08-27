"""Perplexity Search API provider（官方 SDK）。"""

from __future__ import annotations

from perplexity import AsyncPerplexity

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
)


class PerplexityProvider(WebSearchProvider):
    name = "perplexity"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("Perplexity 未配置 API Key")

        client = AsyncPerplexity(api_key=config.api_key)
        try:
            try:
                response = await client.search.create(
                    query=query,
                    max_results=config.max_results,
                )
            except Exception as exc:
                raise ToolExecutionError(f"Perplexity 搜索失败: {exc}") from exc
        finally:
            await client.close()

        results = [
            WebSearchResult(
                title=item.title or "",
                url=item.url or "",
                snippet=item.snippet or "",
            )
            for item in response.results or []
        ]
        return WebSearchResponse(results=results)
