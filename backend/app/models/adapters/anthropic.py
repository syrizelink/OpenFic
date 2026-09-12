# -*- coding: utf-8 -*-
"""
Anthropic Adapter - adapter Anthropic API.
"""

from collections.abc import Mapping

import httpx

from app.models.adapters.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Adapter Anthropic API, hanya mendukung model LLM (tidak mendukung embedding)."""

    @property
    def provider_type(self) -> str:
        return "anthropic"

    def supports_embedding(self) -> bool:
        """Anthropic tidak mendukung embedding."""
        return False

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model LLM (telah didefinisikan sebelumnya)."""
        return [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
        ]

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Anthropic tidak mendukung model embedding."""
        return []
