# -*- coding: utf-8 -*-
"""
OpenRouter Adapter - OpenRouter API适配器。
"""

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class OpenRouterAdapter(BaseAdapter):
    """OpenRouter API适配器，支持LLM和Embedding模型。"""

    @property
    def provider_type(self) -> str:
        return "openrouter"

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取LLM模型列表（/models端点）。"""
        url = f"{self._normalize_url(base_url)}/models"
        headers = self._build_auth_header(api_key)

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
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取Embedding模型列表（/embeddings/models端点）。"""
        url = f"{self._normalize_url(base_url)}/embeddings/models"
        headers = self._build_auth_header(api_key)

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
