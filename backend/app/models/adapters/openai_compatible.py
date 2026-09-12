# -*- coding: utf-8 -*-
"""
OpenAI Compatible Adapter - adapter API kompatibel OpenAI.

Digunakan untuk mendukung berbagai layanan pihak ketiga yang kompatibel dengan
OpenAI (misalnya Ollama, vLLM, dll).
Karena ini antarmuka kompatibel umum, LLM dan embedding tidak dapat dibedakan,
sehingga kedua metode mengembalikan seluruh daftar model.
"""

import httpx
from loguru import logger
from collections.abc import Mapping

from app.models.adapters.base import BaseAdapter


class OpenAICompatibleAdapter(BaseAdapter):
    """Adapter API kompatibel OpenAI, mendukung LLM dan embedding."""

    @property
    def provider_type(self) -> str:
        return "openai-compatible"

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model (mengembalikan semua model yang tersedia)."""
        return await self._fetch_all_models(client, base_url, api_key, headers=headers)

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model (semua model tersedia, dipilih sendiri oleh pengguna)."""
        return await self._fetch_all_models(client, base_url, api_key, headers=headers)

    async def get_rerank_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil daftar model (semua model tersedia, dipilih sendiri oleh pengguna)."""
        return await self._fetch_all_models(client, base_url, api_key, headers=headers)

    def supports_rerank(self) -> bool:
        return True

    async def _fetch_all_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Ambil semua model yang tersedia."""
        url = self._normalize_url(base_url)
        url = f"{url}/models" if url.endswith("/v1") else f"{url}/v1/models"
        request_headers = self._build_auth_header(api_key, headers)

        try:
            response = await client.get(url, headers=request_headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                model_name = model.get("name", model_id) if model.get("name") else model_id
                models.append({"id": model_id, "name": model_name})

            return models
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 429} or exc.response.status_code >= 500:
                raise
            logger.warning(f"Failed to fetch models from OpenAI-compatible API: {exc}")
            # Kembalikan daftar kosong, pengguna dapat memasukkan model ID manual
            return []
        except httpx.HTTPError as exc:
            logger.warning(f"Failed to fetch models from OpenAI-compatible API: {exc}")
            # Kembalikan daftar kosong, pengguna dapat memasukkan model ID manual
            return []
