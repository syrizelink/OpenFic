"""联网搜索 provider 的统一抽象与共享 HTTP 工具。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, Field

DEFAULT_HTTP_TIMEOUT = 30.0


class WebSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""


class WebSearchResponse(BaseModel):
    answer: str | None = None
    results: list[WebSearchResult] = Field(default_factory=list)


@dataclass(frozen=True)
class WebSearchProviderConfig:
    api_key: str = ""
    max_results: int = 8
    extras: dict[str, str] = field(default_factory=dict)

    def extra(self, key: str, default: str = "") -> str:
        value = self.extras.get(key, default)
        return value.strip() if isinstance(value, str) else default


class WebSearchProvider(ABC):
    name: ClassVar[str]

    @abstractmethod
    async def search(
        self,
        query: str,
        config: WebSearchProviderConfig,
    ) -> WebSearchResponse: ...


async def http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    async with httpx.AsyncClient(
        timeout=DEFAULT_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


async def http_post_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    async with httpx.AsyncClient(
        timeout=DEFAULT_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def http_error_message(provider_name: str, exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        detail = (exc.response.text or "").strip()[:200]
        return (
            f"{provider_name} 返回 HTTP {exc.response.status_code}"
            + (f": {detail}" if detail else "")
        )
    if isinstance(exc, httpx.HTTPError):
        return f"{provider_name} 请求失败: {exc}"
    return f"{provider_name} 搜索失败: {exc}"
