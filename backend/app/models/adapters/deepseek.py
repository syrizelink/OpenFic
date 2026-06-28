# -*- coding: utf-8 -*-
"""
DeepSeek Adapter - DeepSeek API适配器。

DeepSeek API兼容OpenAI格式，仅支持LLM，不支持Embedding。
"""

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class DeepSeekAdapter(BaseAdapter):
    """DeepSeek API适配器，仅支持LLM。"""

    @property
    def provider_type(self) -> str:
        return "deepseek"

    def supports_embedding(self) -> bool:
        """DeepSeek不支持Embedding。"""
        return False

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
                models.append({"id": model_id, "name": model_id})
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch DeepSeek models: {e}")
            # 返回预定义列表作为fallback
            return [
                {"id": "deepseek-chat", "name": "DeepSeek Chat"},
                {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
            ]

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """DeepSeek不支持Embedding模型。"""
        return []
