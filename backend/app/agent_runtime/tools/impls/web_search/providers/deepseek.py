"""DeepSeek Search API provider。"""

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

DEEPSEEK_SEARCH_URL = "https://api.deepseek.com/v1/tools/search"
MAX_DEEPSEEK_QUERY_LENGTH = 128


class DeepSeekProvider(WebSearchProvider):
    name = "deepseek"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("DeepSeek 未配置 API Key")
        if len(query) > MAX_DEEPSEEK_QUERY_LENGTH:
            raise ToolExecutionError("DeepSeek 搜索查询不能超过 128 个字符")

        try:
            payload = await http_post_json(
                DEEPSEEK_SEARCH_URL,
                headers={"Authorization": f"Bearer {config.api_key}"},
                payload={"query": query, "count": config.max_results},
                trust_env=config.trust_proxy_environment,
            )
        except Exception as exc:
            raise ToolExecutionError(http_error_message("DeepSeek", exc)) from exc

        raw_results = payload.get("results") if isinstance(payload, dict) else []
        results = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                snippet=item.get("summary") or item.get("snippet") or "",
            )
            for item in raw_results or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=results)
