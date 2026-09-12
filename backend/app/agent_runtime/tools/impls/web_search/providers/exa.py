"""Provider Exa API (SDK resmi)."""

from __future__ import annotations

import httpx
from exa_py import AsyncExa

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProvider,
    WebSearchProviderConfig,
    WebSearchResponse,
    WebSearchResult,
)

EXA_SNIPPET_MAX_CHARS = 300


class ExaProvider(WebSearchProvider):
    name = "exa"

    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse:
        if not config.api_key:
            raise ToolExecutionError("API Key Exa belum dikonfigurasi")

        client = AsyncExa(api_key=config.api_key)
        http_client = None
        if not config.trust_proxy_environment:
            http_client = httpx.AsyncClient(
                base_url=client.base_url,
                headers=client.headers,
                timeout=600,
                trust_env=False,
            )
            client._client = http_client

        try:
            response = await client.search(
                query,
                num_results=config.max_results,
                contents={
                    "highlights": True,
                    "text": {"max_characters": EXA_SNIPPET_MAX_CHARS},
                },
            )
        except Exception as exc:
            raise ToolExecutionError(f"Pencarian Exa gagal: {exc}") from exc
        finally:
            if http_client is not None:
                await http_client.aclose()

        results = []
        for item in response.results:
            if item.highlights:
                snippet = "\n".join(highlight for highlight in item.highlights if highlight)
            else:
                snippet = item.text or ""
            results.append(
                WebSearchResult(
                    title=item.title or "",
                    url=item.url or "",
                    snippet=snippet[:EXA_SNIPPET_MAX_CHARS],
                )
            )
        return WebSearchResponse(results=results)
