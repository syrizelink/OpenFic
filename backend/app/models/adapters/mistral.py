# -*- coding: utf-8 -*-
"""
Mistral AI Adapter - Mistral API适配器。

Mistral API兼容OpenAI格式，支持LLM和Embedding。
"""

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class MistralAdapter(BaseAdapter):
    """Mistral API适配器，支持LLM和Embedding。"""

    @property
    def provider_type(self) -> str:
        return "mistral"

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取LLM模型列表。"""
        url = f"{self._normalize_url(base_url)}/models"
        headers = self._build_auth_header(api_key)

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                # 排除embedding模型（Mistral API混合返回）
                if "embed" not in model_id.lower():
                    models.append({"id": model_id, "name": model_id})
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch Mistral LLM models: {e}")
            # 返回预定义列表作为fallback
            return [
                {"id": "mistral-large-latest", "name": "Mistral Large"},
                {"id": "mistral-medium-latest", "name": "Mistral Medium"},
                {"id": "mistral-small-latest", "name": "Mistral Small"},
                {"id": "codestral-latest", "name": "Codestral"},
            ]

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取Embedding模型列表。"""
        url = f"{self._normalize_url(base_url)}/models"
        headers = self._build_auth_header(api_key)

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                # 只包含embedding模型
                if "embed" in model_id.lower():
                    models.append({"id": model_id, "name": model_id})
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch Mistral embedding models: {e}")
            # 返回预定义列表作为fallback
            return [
                {"id": "mistral-embed", "name": "Mistral Embed"},
            ]
