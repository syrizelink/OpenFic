"""Anthropic-compatible adapter without a model discovery endpoint."""

import httpx

from app.models.adapters.base import BaseAdapter


class AnthropicCompatibleAdapter(BaseAdapter):
    """Anthropic-compatible provider adapter supporting LLM calls only."""

    @property
    def provider_type(self) -> str:
        return "anthropic-compatible"

    def supports_embedding(self) -> bool:
        return False

    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return []

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return []
