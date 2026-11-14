"""
Opper Adapter - Opper API适配器。
"""

from collections.abc import Mapping
from typing import Any

import httpx
from loguru import logger

from app.models.adapters.base import BaseAdapter
from app.models.helpers.opper_attribution import get_opper_attribution_headers


class OpperAdapter(BaseAdapter):
    """Opper API适配器，支持LLM和Embedding模型。"""

    @property
    def provider_type(self) -> str:
        return "opper"

    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """获取LLM模型列表（/models端点中 opper.type 为 llm 的模型）。"""
        url = f"{self._normalize_url(base_url)}/models"
        request_headers = self._build_headers(api_key, headers)

        try:
            data = await self._fetch_models(client, url, request_headers)
        except Exception as e:
            logger.error(f"Failed to fetch Opper LLM models: {e}")
            raise

        return self._filter_models(data, "llm")

    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """获取Embedding模型列表（/models端点中 opper.type 为 embedding 的模型）。"""
        url = f"{self._normalize_url(base_url)}/models"
        request_headers = self._build_headers(api_key, headers)

        try:
            data = await self._fetch_models(client, url, request_headers)
        except Exception as e:
            logger.error(f"Failed to fetch Opper embedding models: {e}")
            raise

        return self._filter_models(data, "embedding")

    def _filter_models(
        self, data: list[dict[str, Any]], model_type: str
    ) -> list[dict[str, str]]:
        models: list[dict[str, str]] = []
        seen: set[str] = set()
        for model in data:
            model_id = model.get("id", "")
            opper = model.get("opper") or {}
            if (
                not model_id
                or model_id in seen
                or opper.get("type", "llm") != model_type
            ):
                continue
            seen.add(model_id)
            models.append(
                {"id": model_id, "name": opper.get("display_name") or model_id}
            )
        return models

    def _build_headers(
        self, api_key: str, headers: Mapping[str, str] | None
    ) -> dict[str, str]:
        return {
            **get_opper_attribution_headers(),
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
