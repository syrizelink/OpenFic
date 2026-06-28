# -*- coding: utf-8 -*-
"""
Anthropic Adapter - Anthropic API适配器。
"""

import httpx

from app.models.adapters.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Anthropic API适配器，仅支持LLM模型（不支持Embedding）。"""

    @property
    def provider_type(self) -> str:
        return "anthropic"

    def supports_embedding(self) -> bool:
        """Anthropic不支持Embedding。"""
        return False

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取LLM模型列表（预定义）。"""
        return [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
        ]

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """Anthropic不支持Embedding模型。"""
        return []
