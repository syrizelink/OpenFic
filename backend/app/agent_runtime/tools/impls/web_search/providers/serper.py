"""Serper (Google) API provider。"""

from __future__ import annotations

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
    http_error_message,
    http_post_json,
)

SERPER_SEARCH_URL = "https://google.serper.dev/search"


class SerperProvider(WebSearchProvider):
    name = "serper"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("Serper 未配置 API Key")

        try:
            payload = await http_post_json(
                SERPER_SEARCH_URL,
                headers={"X-API-KEY": config.api_key},
                payload={"q": query, "num": config.max_results},
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message(self.name, exc)) from exc

        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("link") or "",
                snippet=item.get("snippet") or "",
            )
            for item in (payload or {}).get("organic") or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
