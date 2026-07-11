# -*- coding: utf-8 -*-
"""
OpenAI Compatible Adapter - OpenAI兼容API适配器。

用于支持各种OpenAI兼容的第三方服务（如Ollama、vLLM等）。
由于是通用兼容接口，无法区分LLM和Embedding，两个方法都返回全部模型列表。
"""

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class OpenAICompatibleAdapter(BaseAdapter):
    """OpenAI兼容API适配器，支持LLM和Embedding。"""

    @property
    def provider_type(self) -> str:
        return "openai-compatible"

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取模型列表（返回全部可用模型）。"""
        return await self._fetch_all_models(client, base_url, api_key)

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取模型列表（返回全部可用模型，由用户自行选择）。"""
        return await self._fetch_all_models(client, base_url, api_key)

    async def get_rerank_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取模型列表（返回全部可用模型，由用户自行选择）。"""
        return await self._fetch_all_models(client, base_url, api_key)

    def supports_rerank(self) -> bool:
        return True

    async def _fetch_all_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取所有可用模型。"""
        url = f"{self._normalize_url(base_url)}/models"
        headers = self._build_auth_header(api_key) if api_key else {}

        try:
            response = await client.get(url, headers=headers)
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
            # 返回空列表，允许用户手动输入模型ID
            return []
        except httpx.HTTPError as exc:
            logger.warning(f"Failed to fetch models from OpenAI-compatible API: {exc}")
            # 返回空列表，允许用户手动输入模型ID
            return []
