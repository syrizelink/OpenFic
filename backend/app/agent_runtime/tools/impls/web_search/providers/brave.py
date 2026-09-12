"""Provider Brave Search API."""

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

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider(WebSearchProvider):
    name = "brave"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("API Key Brave belum dikonfigurasi")

        url = f"{BRAVE_SEARCH_URL}?{urlencode({'q': query, 'count': config.max_results})}"
        try:
            payload = await http_get_json(
                url,
                headers={
                    "X-Subscription-Token": config.api_key,
                    "Accept": "application/json",
                },
                trust_env=config.trust_proxy_environment,
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message(self.name, exc)) from exc

        web = (payload or {}).get("web") or {}
        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=item.get("description") or "",
            )
            for item in web.get("results") or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
