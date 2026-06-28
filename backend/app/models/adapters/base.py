# -*- coding: utf-8 -*-
"""
Base Adapter - 适配器基类。

每个 Provider 对应一个 Adapter，负责暴露不同任务类型的模型列表。
"""

from abc import ABC, abstractmethod

import httpx


class BaseAdapter(ABC):
    """
    Adapter基类，定义Provider协议转换接口。

    每个具体的Adapter负责：
    1. 获取该Provider支持的LLM模型列表
    2. 获取该Provider支持的Embedding模型列表
    3. 获取该Provider支持的Rerank模型列表
    """

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """返回该Adapter对应的provider类型标识。"""
        pass

    @abstractmethod
    async def get_llm_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        获取LLM模型列表。

        Args:
            client: HTTP客户端。
            base_url: Provider的API基础URL。
            api_key: API Key（明文）。

        Returns:
            模型列表，每个元素为 {"id": "model-id", "name": "Model Name"}。
        """
        pass

    @abstractmethod
    async def get_embedding_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        获取Embedding模型列表。

        Args:
            client: HTTP客户端。
            base_url: Provider的API基础URL。
            api_key: API Key（明文）。

        Returns:
            模型列表，每个元素为 {"id": "model-id", "name": "Model Name"}。
        """
        pass

    async def get_rerank_models(
        self, client: httpx.AsyncClient, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        获取 Rerank 模型列表。

        默认回退到 LLM 模型列表，适用于只能列出通用 `/models` 的 provider。
        """
        return await self.get_llm_models(client, base_url, api_key)

    def supports_llm(self) -> bool:
        """检查该Adapter是否支持LLM模型。默认支持。"""
        return True

    def supports_embedding(self) -> bool:
        """检查该Adapter是否支持Embedding模型。默认支持。"""
        return True

    def supports_rerank(self) -> bool:
        """检查该Adapter是否支持Rerank模型。默认不支持。"""
        return False

    # ========================
    # 工具方法
    # ========================

    def _build_auth_header(self, api_key: str) -> dict[str, str]:
        """构建Bearer认证头。"""
        return {"Authorization": f"Bearer {api_key}"}

    def _normalize_url(self, url: str) -> str:
        """规范化URL，移除末尾斜杠。"""
        return url.rstrip("/")
