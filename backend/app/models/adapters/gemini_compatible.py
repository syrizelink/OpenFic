"""Gemini-compatible provider adapter."""

from collections.abc import Mapping

import httpx

from app.models.adapters.base import BaseAdapter


class GeminiCompatibleAdapter(BaseAdapter):
    """Gemini native provider adapter supporting LLM model discovery only."""

    @property
    def provider_type(self) -> str:
        return "gemini-compatible"

    def supports_embedding(self) -> bool:
        return False

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        url = self._normalize_url(base_url)
        models_url = (
            f"{url}/models" if url.endswith("/v1beta") else f"{url}/v1beta/models"
        )
        request_headers = {
            key: value
            for key, value in (headers or {}).items()
            if key.lower() != "x-goog-api-key"
        }
        request_headers["x-goog-api-key"] = api_key
        response = await client.get(
            models_url,
            headers=request_headers,
        )
        response.raise_for_status()
        data = response.json()

        models: list[dict[str, str]] = []
        for model in data.get("models", []):
            if not isinstance(model, dict):
                continue
            model_name = model.get("name")
            methods = model.get("supportedGenerationMethods")
            if not isinstance(model_name, str):
                continue
            if methods is not None and (
                not isinstance(methods, list) or "generateContent" not in methods
            ):
                continue

            model_id = model_name.removeprefix("models/")
            if not model_id:
                continue
            display_name = model.get("displayName")
            models.append(
                {
                    "id": model_id,
                    "name": display_name if isinstance(display_name, str) else model_id,
                }
            )
        return models

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        return []
