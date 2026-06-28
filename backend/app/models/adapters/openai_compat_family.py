# -*- coding: utf-8 -*-
"""OpenAI-compatible provider adapters with distinct provider_type values."""

import httpx
from loguru import logger

from app.models.adapters.openai_compatible import OpenAICompatibleAdapter


class OllamaAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "ollama"

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return await self._fetch_tags(client, base_url)

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return await self._fetch_tags(client, base_url)

    def supports_rerank(self) -> bool:
        return False

    async def _fetch_tags(
        self, client: httpx.AsyncClient, base_url: str
    ) -> list[dict[str, str]]:
        url = f"{self._normalize_url(base_url)}/api/tags"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("Failed to fetch Ollama tags: {}", exc)
            return []

        models: list[dict[str, str]] = []
        for model in data.get("models", []):
            model_name = model.get("name", "")
            if not model_name:
                continue
            models.append({"id": model_name, "name": model_name})
        return models


class GroqAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "groq"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False


class HuggingFaceAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "huggingface"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False


class NvidiaAIEndpointsAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "nvidia-ai-endpoints"

    def supports_embedding(self) -> bool:
        return True

    def supports_rerank(self) -> bool:
        return True


class CohereAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "cohere"

    def supports_embedding(self) -> bool:
        return True

    def supports_rerank(self) -> bool:
        return False


class AmazonNovaAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "amazon-nova"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False
