"""You.com Search API provider。"""

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

YOUCOM_SEARCH_URL = "https://ydc-index.io/v1/search"


class YouComProvider(WebSearchProvider):
    name = "youcom"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("You.com 未配置 API Key")

        try:
            payload = await http_post_json(
                YOUCOM_SEARCH_URL,
                headers={"X-API-Key": config.api_key},
                payload={"query": query, "count": config.max_results},
                trust_env=config.trust_proxy_environment,
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message(self.name, exc)) from exc

        results_payload = (payload or {}).get("results") or {}
        web = results_payload.get("web") if isinstance(results_payload, dict) else None
        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=item.get("description")
                or next(iter(item.get("snippets") or []), ""),
            )
            for item in web or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
