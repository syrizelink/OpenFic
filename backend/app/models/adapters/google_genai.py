# -*- coding: utf-8 -*-
"""
Google Generative AI Adapter - Google API适配器。

Google AI API通过supportedGenerationMethods字段区分模型类型：
- generateContent: LLM模型
- embedContent: Embedding模型
"""

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter


class GoogleGenAIAdapter(BaseAdapter):
    """Google Generative AI适配器，支持LLM和Embedding。"""

    @property
    def provider_type(self) -> str:
        return "google-genai"

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取LLM模型列表（supportedGenerationMethods包含generateContent）。"""
        url = f"{self._normalize_url(base_url)}/models"
        
        try:
            response = await client.get(url, params={"key": api_key})
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("models", []):
                methods = model.get("supportedGenerationMethods", [])
                # LLM模型支持generateContent
                if "generateContent" in methods:
                    model_name = model.get("name", "")
                    if model_name.startswith("models/"):
                        model_id = model_name[7:]
                    else:
                        model_id = model_name
                    display_name = model.get("displayName", model_id)
                    models.append({"id": model_id, "name": display_name})

            return models
        except Exception as e:
            logger.warning(f"Failed to fetch Google GenAI LLM models: {e}")
            # 返回预定义列表作为fallback
            return [
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
                {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite"},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
            ]

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取Embedding模型列表（supportedGenerationMethods包含embedContent）。"""
        url = f"{self._normalize_url(base_url)}/models"
        
        try:
            response = await client.get(url, params={"key": api_key})
            response.raise_for_status()
            data = response.json()

            models = []
            for model in data.get("models", []):
                methods = model.get("supportedGenerationMethods", [])
                # Embedding模型支持embedContent
                if "embedContent" in methods:
                    model_name = model.get("name", "")
                    if model_name.startswith("models/"):
                        model_id = model_name[7:]
                    else:
                        model_id = model_name
                    display_name = model.get("displayName", model_id)
                    models.append({"id": model_id, "name": display_name})

            return models
        except Exception as e:
            logger.warning(f"Failed to fetch Google GenAI embedding models: {e}")
            # 返回预定义列表作为fallback
            return [
                {"id": "text-embedding-004", "name": "Text Embedding 004"},
                {"id": "embedding-001", "name": "Embedding 001"},
            ]
