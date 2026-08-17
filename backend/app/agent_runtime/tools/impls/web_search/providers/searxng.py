"""SearXNG 自托管实例 provider。"""

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


class SearxngProvider(WebSearchProvider):
    name = "searxng"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        base_url = config.extra("searxng_base_url")
        if not base_url:
            raise ToolExecutionError(
                "SearXNG 未配置 searxng_base_url（自托管实例地址）"
            )

        url = (
            f"{base_url.rstrip('/')}/search?"
            f"{urlencode({'q': query, 'format': 'json', 'safesearch': '0'})}"
        )
        try:
            payload = await http_get_json(url)
        except Exception as exc:
            raise ToolExecutionError(http_error_message(self.name, exc)) from exc

        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=item.get("content") or "",
            )
            for item in (payload or {}).get("results") or []
            if isinstance(item, dict)
        ][: config.max_results]
        return WebSearchResponse(results=results)
