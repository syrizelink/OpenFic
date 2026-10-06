"""Account-scoped model catalog for the OpenAI Codex provider."""

from collections.abc import Mapping

import httpx

from app.models.adapters.openai_responses_compatible import (
    OpenAIResponsesCompatibleAdapter,
)
from app.models.services.openai_codex_service import OPENAI_CODEX_PROVIDER_TYPE


class OpenAICodexAdapter(OpenAIResponsesCompatibleAdapter):
    """Read the account-specific ``models`` response used by OpenAI Codex OAuth."""

    @property
    def provider_type(self) -> str:
        return OPENAI_CODEX_PROVIDER_TYPE

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        response = await client.get(
            f"{self._normalize_url(base_url)}/models",
            headers=self._build_auth_header(api_key, headers),
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise ValueError("OpenAI Codex 模型列表响应缺少 models 数组")
        return [
            {
                "id": item["slug"],
                "name": item.get("display_name") or item["slug"],
            }
            for item in models
            if isinstance(item, dict)
            and isinstance(item.get("slug"), str)
            and item.get("visibility") == "list"
        ]

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False
