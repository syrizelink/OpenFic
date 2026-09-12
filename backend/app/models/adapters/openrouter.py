# -*- coding: utf-8 -*-
"""
OpenRouter Adapter - adapter OpenRouter API.
"""

from collections.abc import Mapping

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter
from app.models.helpers.openrouter_attribution import get_openrouter_attribution_headers


class OpenRouterAdapter(BaseAdapter):
    """Adapter OpenRouter API, mendukung model LLM dan embedding."""

    @property
    def provider_type(self) -> str:
        return "openrouter"

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model LLM (endpoint /models)."""
        url = f"{self._normalize_url(base_url)}/models"
        headers = {
            **self._build_auth_header(api_key),
            **get_openrouter_attribution_headers(),
        }

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                model_name = model.get("name", model_id)
                models.append({"id": model_id, "name": model_name})

            return models
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter LLM models: {e}")
            raise

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model embedding (endpoint /embeddings/models)."""
        url = f"{self._normalize_url(base_url)}/embeddings/models"
        headers = {
            **self._build_auth_header(api_key),
            **get_openrouter_attribution_headers(),
        }

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                model_name = model.get("name", model_id)
                models.append({"id": model_id, "name": model_name})

            return models
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter embedding models: {e}")
            raise

    def supports_rerank(self) -> bool:
        return True
