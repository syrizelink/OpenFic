# -*- coding: utf-8 -*-
"""Catalog icon proxy with in-memory source selection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx

CatalogIconSource = Literal["models_dev", "jsdelivr"]


@dataclass(frozen=True)
class CatalogIconPayload:
    content: bytes
    source: CatalogIconSource


@dataclass(frozen=True)
class _IconSourceConfig:
    name: CatalogIconSource
    url_template: str


@dataclass(frozen=True)
class _IconSourceError(Exception):
    source: CatalogIconSource
    status_code: int | None
    should_switch_winner: bool


class CatalogIconProxyError(Exception):
    """Raised when no upstream source can serve the requested icon."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


_ICON_SOURCES: tuple[_IconSourceConfig, ...] = (
    _IconSourceConfig("models_dev", "https://models.dev/logos/{provider_id}.svg"),
    _IconSourceConfig(
        "jsdelivr",
        "https://cdn.jsdelivr.net/gh/sst/models.dev@dev/providers/{provider_id}/logo.svg",
    ),
)
_SOURCE_BY_NAME = {source.name: source for source in _ICON_SOURCES}


class CatalogIconProxyService:
    """Serve catalog icons through a single backend entrypoint."""

    def __init__(self, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self._winner: CatalogIconSource | None = None
        self._probe_lock = asyncio.Lock()
        self._switch_lock = asyncio.Lock()

    @property
    def winner(self) -> CatalogIconSource | None:
        return self._winner

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_icon(self, provider_id: str) -> CatalogIconPayload:
        if not provider_id:
            raise CatalogIconProxyError(404, "Catalog provider icon not found")

        if self._winner is None:
            async with self._probe_lock:
                if self._winner is None:
                    result = await self._probe_sources(provider_id)
                    self._winner = result.source
                    return result

        primary_source = self._winner
        if primary_source is None:
            raise CatalogIconProxyError(502, "Catalog icon source is unavailable")
        return await self._fetch_with_fallback(provider_id, primary_source)

    async def _probe_sources(self, provider_id: str) -> CatalogIconPayload:
        tasks = [
            asyncio.create_task(self._fetch_from_source(source, provider_id))
            for source in _ICON_SOURCES
        ]
        errors: list[_IconSourceError] = []

        try:
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                except _IconSourceError as exc:
                    errors.append(exc)
                    continue

                for pending in tasks:
                    if pending is not task and not pending.done():
                        pending.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                return result
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        raise self._terminal_error(provider_id, errors)

    async def _fetch_with_fallback(
        self, provider_id: str, primary_source_name: CatalogIconSource
    ) -> CatalogIconPayload:
        primary_source = _SOURCE_BY_NAME[primary_source_name]
        fallback_source = next(
            source for source in _ICON_SOURCES if source.name != primary_source_name
        )

        try:
            return await self._fetch_from_source(primary_source, provider_id)
        except _IconSourceError as primary_error:
            try:
                fallback_result = await self._fetch_from_source(fallback_source, provider_id)
            except _IconSourceError as fallback_error:
                raise self._terminal_error(provider_id, [primary_error, fallback_error])

            if primary_error.should_switch_winner:
                async with self._switch_lock:
                    if self._winner == primary_source_name:
                        self._winner = fallback_source.name
            return fallback_result

    async def _fetch_from_source(
        self, source: _IconSourceConfig, provider_id: str
    ) -> CatalogIconPayload:
        url = source.url_template.format(provider_id=provider_id)
        try:
            response = await self._client.get(url)
        except httpx.TimeoutException as exc:
            raise _IconSourceError(source.name, None, True) from exc
        except httpx.RequestError as exc:
            raise _IconSourceError(source.name, None, True) from exc

        if response.status_code == 200:
            return CatalogIconPayload(content=response.content, source=source.name)
        if response.status_code == 404:
            raise _IconSourceError(source.name, 404, False)
        if 500 <= response.status_code <= 599:
            raise _IconSourceError(source.name, response.status_code, True)
        raise _IconSourceError(source.name, response.status_code, False)

    def _terminal_error(
        self, provider_id: str, errors: list[_IconSourceError]
    ) -> CatalogIconProxyError:
        if errors and all(error.status_code == 404 for error in errors):
            return CatalogIconProxyError(
                404,
                f"Catalog provider icon '{provider_id}' was not found",
            )
        return CatalogIconProxyError(
            502,
            f"Failed to fetch catalog provider icon '{provider_id}'",
        )
