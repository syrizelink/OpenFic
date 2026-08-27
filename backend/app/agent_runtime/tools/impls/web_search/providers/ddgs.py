"""DuckDuckGo（ddgs）provider。"""

from __future__ import annotations

import asyncio
from typing import Any

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from loguru import logger

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
)

DDGS_MAX_ATTEMPTS = 2


def _run_sync_search(query: str, config: WebSearchProviderConfig) -> Any:
    with DDGS() as ddgs:
        return ddgs.text(
            query,
            max_results=config.max_results,
            region="wt-wt",
            safesearch="moderate",
            backend=config.extra("ddgs_backend", "auto"),
        )


async def _search_with_retry(query: str, config: WebSearchProviderConfig) -> Any:
    for attempt in range(DDGS_MAX_ATTEMPTS):
        try:
            return await asyncio.to_thread(_run_sync_search, query, config)
        except DDGSException as exc:
            if attempt + 1 >= DDGS_MAX_ATTEMPTS:
                raise
            logger.warning(
                "DDGS 聚合搜索失败，准备重试 attempt={}/{} error={}",
                attempt + 1,
                DDGS_MAX_ATTEMPTS,
                exc,
            )
    raise RuntimeError("DDGS 搜索重试流程异常结束")


class DdgsProvider(WebSearchProvider):
    name = "ddgs"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        try:
            results = await _search_with_retry(query, config)
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
