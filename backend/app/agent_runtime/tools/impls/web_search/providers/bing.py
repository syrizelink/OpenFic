"""Bing Web Search API v7 provider。"""

from __future__ import annotations

from urllib.parse import urlencode

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
    http_error_message,
    http_get_json,
)

BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"


class BingProvider(WebSearchProvider):
    name = "bing"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("Bing 未配置 API Key")

        mkt = config.extra("bing_mkt", "zh-CN")
        url = f"{BING_SEARCH_URL}?{urlencode({'q': query, 'count': config.max_results, 'mkt': mkt, 'safeSearch': 'Moderate'})}"
        try:
            payload = await http_get_json(
                url,
                headers={"Ocp-Apim-Subscription-Key": config.api_key},
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message(self.name, exc)) from exc

        web_pages = (payload or {}).get("webPages") or {}
        results = [
            WebSearchResult(
                title=item.get("name") or "",
                url=item.get("url") or "",
                snippet=item.get("snippet") or "",
            )
            for item in web_pages.get("value") or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
