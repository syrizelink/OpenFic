"""
Requesty Adapter - Requesty API适配器。
"""

from collections.abc import Mapping
from typing import Any

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter
from app.models.helpers.requesty_attribution import get_requesty_attribution_headers


class RequestyAdapter(BaseAdapter):
    """Requesty API适配器，支持LLM和Embedding模型。"""

    @property
    def provider_type(self) -> str:
        return "requesty"

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """获取LLM模型列表（优先 /models/managed 托管策略，再合并 /models 完整目录）。"""
        base = self._normalize_url(base_url)
        request_headers = self._build_headers(api_key, headers)

        managed: list[dict[str, Any]] = []
        try:
            managed = await self._fetch_models(
                client, f"{base}/models/managed", request_headers
            )
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"Failed to fetch Requesty managed models: {e}")

        try:
            catalog = await self._fetch_models(
                client, f"{base}/models", request_headers
            )
        except Exception as e:
            logger.error(f"Failed to fetch Requesty LLM models: {e}")
            raise

        models: list[dict[str, str]] = []
        seen: set[str] = set()
        for model in [*managed, *catalog]:
            model_id = model.get("id", "")
            if not model_id or model_id in seen or model.get("api", "chat") != "chat":
                continue
            seen.add(model_id)
            models.append({"id": model_id, "name": model_id})

        return models

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """获取Embedding模型列表（/models端点中 api 为 embedding 的模型）。"""
        url = f"{self._normalize_url(base_url)}/models"
        request_headers = self._build_headers(api_key, headers)

        try:
            data = await self._fetch_models(client, url, request_headers)
        except Exception as e:
            logger.error(f"Failed to fetch Requesty embedding models: {e}")
            raise

        return [
            {"id": model["id"], "name": model["id"]}
            for model in data
            if model.get("id") and model.get("api") == "embedding"
        ]

    def _build_headers(
        self, api_key: str, headers: Mapping[str, str] | None
    ) -> dict[str, str]:
        return {
            **get_requesty_attribution_headers(),
            **self._build_auth_header(api_key, headers),
        }

    async def _fetch_models(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("data", [])
