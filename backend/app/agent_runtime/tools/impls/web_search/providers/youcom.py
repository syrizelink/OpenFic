"""You.com Search API provider (works with no API key)."""

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

YOUCOM_KEYLESS_SEARCH_URL = "https://api.you.com/v1/agents/search"
YOUCOM_KEYED_SEARCH_URL = "https://ydc-index.io/v1/search"
YOUCOM_USER_AGENT = "youdotcom-integration/syrizelink-openfic"
YOUCOM_SNIPPET_MAX_CHARS = 300
YOUCOM_KEYLESS_MAX_COUNT = 50


def _snippet_from_item(item: dict) -> str:
    snippet = item.get("description") or item.get("snippet") or ""
    if not snippet:
        snippets = item.get("snippets")
        if isinstance(snippets, list):
            snippet = " ".join(
                part.strip() for part in snippets if isinstance(part, str)
            )
    return " ".join(str(snippet).split())[:YOUCOM_SNIPPET_MAX_CHARS]


class YouComProvider(WebSearchProvider):
    name = "youcom"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        headers = {"User-Agent": YOUCOM_USER_AGENT}
        if config.api_key:
            url = YOUCOM_KEYED_SEARCH_URL
            headers["X-API-Key"] = config.api_key
            count = config.max_results
        else:
            url = YOUCOM_KEYLESS_SEARCH_URL
            count = min(config.max_results, YOUCOM_KEYLESS_MAX_COUNT)

        try:
            payload = await http_post_json(
                url,
                headers=headers,
                payload={"query": query, "count": count},
                trust_env=config.trust_proxy_environment,
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message("You.com", exc)) from exc

        raw_results = []
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, dict):
                raw_results = results.get("web") or []
            elif isinstance(results, list):
                raw_results = results

        parsed = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=_snippet_from_item(item),
            )
            for item in raw_results or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=parsed)
