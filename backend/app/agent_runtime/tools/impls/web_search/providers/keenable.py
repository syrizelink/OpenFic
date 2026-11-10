"""Keenable Search API provider（无需 API Key）。"""

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

KEENABLE_PUBLIC_SEARCH_URL = "https://api.keenable.ai/v1/search/public"
KEENABLE_SEARCH_URL = "https://api.keenable.ai/v1/search"
KEENABLE_APP_TITLE = "OpenFic"
KEENABLE_SNIPPET_MAX_CHARS = 300


class KeenableProvider(WebSearchProvider):
    name = "keenable"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        # 无 Key 时使用公共接口；若已为 keenable 保存 Key，则改用带 Key 的接口以提升限额。
        url = KEENABLE_PUBLIC_SEARCH_URL
        headers = {"X-Keenable-Title": KEENABLE_APP_TITLE}
        if config.api_key:
            url = KEENABLE_SEARCH_URL
            headers["X-API-Key"] = config.api_key

        try:
            payload = await http_post_json(
                url,
                headers=headers,
                payload={"query": query, "max_results": config.max_results},
                trust_env=config.trust_proxy_environment,
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message("Keenable", exc)) from exc

        raw_results = payload.get("results") if isinstance(payload, dict) else []
        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=" ".join((item.get("snippet") or "").split())[
                    :KEENABLE_SNIPPET_MAX_CHARS
                ],
            )
            for item in raw_results or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
