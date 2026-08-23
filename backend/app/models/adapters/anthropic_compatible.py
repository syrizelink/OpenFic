"""Anthropic-compatible provider adapter."""

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
        url = self._normalize_url(base_url)
        for suffix in ("/anthropic", "/claude"):
            if url.endswith(suffix):
                url = url.removesuffix(suffix)
                break
        if not url.endswith("/v1"):
            url = f"{url}/v1"

        response = await client.get(
            f"{url}/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        response.raise_for_status()
        data = response.json()

        return [
            {
                "id": model_id,
                "name": model.get("display_name", model_id),
            }
            for model in data.get("data", [])
            if (model_id := model.get("id"))
        ]

    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return []
