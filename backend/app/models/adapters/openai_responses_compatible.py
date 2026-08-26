"""OpenAI Responses API-compatible provider adapter."""

import httpx

from app.models.adapters.openai_compatible import OpenAICompatibleAdapter


class OpenAIResponsesCompatibleAdapter(OpenAICompatibleAdapter):
    """Adapter for custom providers exposing the OpenAI Responses API."""

    @property
    def provider_type(self) -> str:
        return "openai-compatible-responses"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return []
