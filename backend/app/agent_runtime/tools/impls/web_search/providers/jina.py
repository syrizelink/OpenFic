"""Jina s.jina.ai 搜索 provider（REST API）。"""

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

JINA_SEARCH_URL = "https://s.jina.ai/"


class JinaProvider(WebSearchProvider):
    name = "jina"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("Jina 未配置 API Key")

        url = f"{JINA_SEARCH_URL}?{urlencode({'q': query, 'num': config.max_results})}"
        try:
            payload = await http_get_json(
                url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Accept": "application/json",
                },
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message(self.name, exc)) from exc

        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=item.get("description") or item.get("content") or "",
            )
            for item in (payload or {}).get("data") or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
