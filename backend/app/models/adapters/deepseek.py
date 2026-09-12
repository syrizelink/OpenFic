# -*- coding: utf-8 -*-
"""
DeepSeek Adapter - adapter DeepSeek API.

DeepSeek API kompatibel dengan format OpenAI, hanya mendukung LLM,
tidak mendukung embedding.
"""

from collections.abc import Mapping

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class DeepSeekAdapter(BaseAdapter):
    """Adapter DeepSeek API, hanya mendukung LLM."""

    @property
    def provider_type(self) -> str:
        return "deepseek"

    def supports_embedding(self) -> bool:
        """DeepSeek tidak mendukung embedding."""
        return False

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model LLM."""
        url = f"{self._normalize_url(base_url)}/models"
        headers = self._build_auth_header(api_key)

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                models.append({"id": model_id, "name": model_id})
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch DeepSeek models: {e}")
            # Kembalikan daftar bawaan sebagai fallback
            return [
                {"id": "deepseek-chat", "name": "DeepSeek Chat"},
                {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
            ]

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """DeepSeek tidak mendukung model embedding."""
        return []
