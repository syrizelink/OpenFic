# -*- coding: utf-8 -*-
"""Catalog icon proxy with per-icon source fallback."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

CatalogIconSource = Literal["models_dev", "jsdelivr", "default"]

_MAX_CONCURRENT_UPSTREAM_REQUESTS = 8
_MODELS_DEV_RETRY_DELAY_SECONDS = 30.0
_DEFAULT_ICON_SVG = b"""<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path shape-rendering="geometricPrecision" d="M9.8132 15.9038L9 18.75L8.1868 15.9038C7.75968 14.4089 6.59112 13.2403 5.09619 12.8132L2.25 12L5.09619 11.1868C6.59113 10.7597 7.75968 9.59112 8.1868 8.09619L9 5.25L9.8132 8.09619C10.2403 9.59113 11.4089 10.7597 12.9038 11.1868L15.75 12L12.9038 12.8132C11.4089 13.2403 10.2403 14.4089 9.8132 15.9038Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M18.2589 8.71454L18 9.75L17.7411 8.71454C17.4388 7.50533 16.4947 6.56117 15.2855 6.25887L14.25 6L15.2855 5.74113C16.4947 5.43883 17.4388 4.49467 17.7411 3.28546L18 2.25L18.2589 3.28546C18.5612 4.49467 19.5053 5.43883 20.7145 5.74113L21.75 6L20.7145 6.25887C19.5053 6.56117 18.5612 7.50533 18.2589 8.71454Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M16.8942 20.5673L16.5 21.75L16.1058 20.5673C15.8818 19.8954 15.3546 19.3682 14.6827 19.1442L13.5 18.75L14.6827 18.3558C15.3546 18.1318 15.8818 17.6046 16.1058 16.9327L16.5 15.75L16.8942 16.9327C17.1182 17.6046 17.6454 18.1318 18.3173 18.3558L19.5 18.75L18.3173 19.1442C17.6454 19.3682 17.1182 19.8954 16.8942 20.5673Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>"""


@dataclass(frozen=True)
class CatalogIconPayload:
    content: bytes
    source: CatalogIconSource


@dataclass(frozen=True)
class _IconSourceConfig:
    name: Literal["models_dev", "jsdelivr"]
    url_template: str


@dataclass(frozen=True)
class _IconSourceError(Exception):
    status_code: int | None
    marks_source_unavailable: bool


class _IconHttpClient(Protocol):
    async def get(self, url: str) -> httpx.Response: ...

    async def aclose(self) -> None: ...


_MODELS_DEV_SOURCE = _IconSourceConfig(
    "models_dev", "https://models.dev/logos/{provider_id}.svg"
)
_JSDELIVR_SOURCE = _IconSourceConfig(
    "jsdelivr",
    "https://cdn.jsdelivr.net/gh/sst/models.dev@dev/providers/{provider_id}/logo.svg",
)


class CatalogIconProxyService:
    """Serve catalog icons through a single backend entrypoint."""

    def __init__(
        self, timeout: float = 5.0, client: _IconHttpClient | None = None
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self._request_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_UPSTREAM_REQUESTS)
        self._models_dev_unavailable_until = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_icon(self, provider_id: str) -> CatalogIconPayload:
        if not provider_id:
            return self._default_icon()

        try:
            return await self._fetch_jsdelivr_icon(provider_id)
        except _IconSourceError:
            return await self._fetch_models_dev_or_default(provider_id)

    async def _fetch_jsdelivr_icon(self, provider_id: str) -> CatalogIconPayload:
        async with self._request_semaphore:
            return await self._request_icon(_JSDELIVR_SOURCE, provider_id)

    async def _fetch_models_dev_or_default(self, provider_id: str) -> CatalogIconPayload:
        if self._is_models_dev_unavailable():
            return self._default_icon()

        async with self._request_semaphore:
            if self._is_models_dev_unavailable():
                return self._default_icon()

            try:
                return await self._request_icon(_MODELS_DEV_SOURCE, provider_id)
            except _IconSourceError as exc:
                if exc.marks_source_unavailable:
                    self._models_dev_unavailable_until = (
                        time.monotonic() + _MODELS_DEV_RETRY_DELAY_SECONDS
                    )
                return self._default_icon()

    async def _request_icon(
        self, source: _IconSourceConfig, provider_id: str
    ) -> CatalogIconPayload:
        url = source.url_template.format(provider_id=provider_id)
        try:
            response = await self._client.get(url)
        except httpx.TimeoutException as exc:
            raise _IconSourceError(None, True) from exc
        except httpx.RequestError as exc:
            raise _IconSourceError(None, True) from exc

        if response.status_code == 200:
            return CatalogIconPayload(content=response.content, source=source.name)
        if response.status_code == 404:
            raise _IconSourceError(404, False)
        if 500 <= response.status_code <= 599:
            raise _IconSourceError(response.status_code, True)
        raise _IconSourceError(response.status_code, False)

    def _is_models_dev_unavailable(self) -> bool:
        return time.monotonic() < self._models_dev_unavailable_until

    @staticmethod
    def _default_icon() -> CatalogIconPayload:
        return CatalogIconPayload(content=_DEFAULT_ICON_SVG, source="default")
