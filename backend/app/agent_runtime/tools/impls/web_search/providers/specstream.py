"""SpecStream Search API provider（需要 API Key）。"""

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

SPECSTREAM_SEARCH_URL = "https://api.specstream.ai/v1/web-search"
SPECSTREAM_SNIPPET_MAX_CHARS = 300


class SpecStreamProvider(WebSearchProvider):
    name = "specstream"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("SpecStream 未配置 API Key")

        try:
            payload = await http_post_json(
                SPECSTREAM_SEARCH_URL,
                headers={"Authorization": f"Bearer {config.api_key}"},
                payload={"q": query, "num": config.max_results},
                trust_env=config.trust_proxy_environment,
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message("SpecStream", exc)) from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            data = {}
        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=" ".join(str(item.get("snippet") or "").split())[
                    :SPECSTREAM_SNIPPET_MAX_CHARS
                ],
            )
            for item in data.get("sources") or []
            if isinstance(item, dict)
        ]
        answer = data.get("answer")
        return WebSearchResponse(
            answer=answer if isinstance(answer, str) and answer.strip() else None,
            results=results,
        )
