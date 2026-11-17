"""
UberLLM Adapter - UberLLM API适配器。
"""

from collections.abc import Mapping

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter
from app.models.helpers.uberllm_attribution import get_uberllm_attribution_headers


class UberLLMAdapter(BaseAdapter):
    """UberLLM API适配器，仅支持LLM（/models 只列出对话模型）。"""

    @property
    def provider_type(self) -> str:
        return "uberllm"

    def supports_embedding(self) -> bool:
        """UberLLM 不提供 Embedding 模型。"""
        return False

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """获取LLM模型列表（/models端点；带 Key 请求时无效 Key 返回 401）。"""
        url = f"{self._normalize_url(base_url)}/models"
        request_headers = {
            **get_uberllm_attribution_headers(),
            **self._build_auth_header(api_key, headers),
        }

        try:
            response = await client.get(url, headers=request_headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch UberLLM LLM models: {e}")
            raise

        return [
            {"id": model["id"], "name": model.get("display_name") or model["id"]}
            for model in data.get("data", [])
            if model.get("id")
        ]

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """UberLLM 不提供 Embedding 模型。"""
        return []
