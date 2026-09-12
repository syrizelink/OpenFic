# -*- coding: utf-8 -*-
"""
OpenAI Adapter - adapter OpenAI API.
"""

from collections.abc import Mapping

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """Adapter OpenAI API, mendukung model LLM dan embedding."""

    @property
    def provider_type(self) -> str:
        return "openai"

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model LLM (melalui API)."""
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
            logger.error(f"Failed to fetch OpenAI LLM models: {e}")
            raise

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model embedding (bawaan, model embedding resmi OpenAI)."""
        return [
            {"id": "text-embedding-3-small", "name": "Text Embedding 3 Small"},
            {"id": "text-embedding-3-large", "name": "Text Embedding 3 Large"},
            {"id": "text-embedding-ada-002", "name": "Text Embedding Ada 002"},
        ]

    def supports_rerank(self) -> bool:
        return True
