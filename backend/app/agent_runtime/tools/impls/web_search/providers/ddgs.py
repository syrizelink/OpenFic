"""DuckDuckGo（ddgs）provider。"""

from __future__ import annotations

import asyncio
from typing import Any

from ddgs import DDGS

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
)


def _run_sync_search(query: str, config: WebSearchProviderConfig) -> Any:
    with DDGS() as ddgs:
        return ddgs.text(
            query,
            max_results=config.max_results,
            region=config.extra("ddgs_region", "wt-wt"),
            safesearch="moderate",
        )


class DdgsProvider(WebSearchProvider):
    name = "ddgs"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        try:
            results = await asyncio.to_thread(_run_sync_search, query, config)
        except Exception as exc:
            raise ToolExecutionError(f"DDGS 搜索失败: {exc}") from exc

        items = [
            WebSearchResult(
                title=item.get("title") or "",
                url=item.get("href") or "",
                snippet=item.get("body") or "",
            )
            for item in results or []
            if isinstance(item, dict)
        ]
        return WebSearchResponse(results=items)
