# -*- coding: utf-8 -*-
"""
Mistral AI Adapter - adapter Mistral API.

Mistral API kompatibel dengan format OpenAI, mendukung LLM dan embedding.
"""

from collections.abc import Mapping

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class MistralAdapter(BaseAdapter):
    """Adapter Mistral API, mendukung LLM dan embedding."""

    @property
    def provider_type(self) -> str:
        return "mistral"

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
                # Kecualikan model embedding (Mistral API mengembalikannya tercampur)
                if "embed" not in model_id.lower():
                    models.append({"id": model_id, "name": model_id})
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch Mistral LLM models: {e}")
            # Kembalikan daftar bawaan sebagai fallback
            return [
                {"id": "mistral-large-latest", "name": "Mistral Large"},
                {"id": "mistral-medium-latest", "name": "Mistral Medium"},
                {"id": "mistral-small-latest", "name": "Mistral Small"},
                {"id": "codestral-latest", "name": "Codestral"},
            ]

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model embedding."""
        url = f"{self._normalize_url(base_url)}/models"
        headers = self._build_auth_header(api_key)

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                # Hanya sertakan model embedding
                if "embed" in model_id.lower():
                    models.append({"id": model_id, "name": model_id})
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch Mistral embedding models: {e}")
            # Kembalikan daftar bawaan sebagai fallback
            return [
                {"id": "mistral-embed", "name": "Mistral Embed"},
            ]
