# -*- coding: utf-8 -*-
"""
Adapter Registry - 适配器注册表。

根据provider_type选择对应的Adapter。
"""

from typing import Type

from app.models.adapters.base import BaseAdapter
from app.models.adapters.anthropic import AnthropicAdapter
from app.models.adapters.deepseek import DeepSeekAdapter
from app.models.adapters.google_genai import GoogleGenAIAdapter
from app.models.adapters.mistral import MistralAdapter
from app.models.adapters.openai import OpenAIAdapter
from app.models.adapters.openai_compat_family import (
    AmazonNovaAdapter,
    CohereAdapter,
    GroqAdapter,
    HuggingFaceAdapter,
    NvidiaAIEndpointsAdapter,
    OllamaAdapter,
)
from app.models.adapters.openai_compatible import OpenAICompatibleAdapter
from app.models.adapters.openrouter import OpenRouterAdapter


class AdapterRegistry:
    """Adapter注册表，管理Provider到Adapter的映射关系。"""

    # Adapter映射关系：provider_type -> Adapter类
    _registry: dict[str, Type[BaseAdapter]] = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "google-genai": GoogleGenAIAdapter,
        "ollama": OllamaAdapter,
        "groq": GroqAdapter,
        "huggingface": HuggingFaceAdapter,
        "deepseek": DeepSeekAdapter,
        "mistral": MistralAdapter,
        "nvidia-ai-endpoints": NvidiaAIEndpointsAdapter,
        "cohere": CohereAdapter,
        "openrouter": OpenRouterAdapter,
        "amazon-nova": AmazonNovaAdapter,
        "openai-compatible": OpenAICompatibleAdapter,
    }

    @classmethod
    def get_adapter(cls, provider_type: str) -> BaseAdapter:
        """
        根据provider_type获取对应的Adapter实例。

        Args:
            provider_type: 提供商类型（如 openai, openrouter等）。

        Returns:
            对应的Adapter实例。

        Raises:
            ValueError: 如果没有找到对应的Adapter。
        """
        adapter_class = cls._registry.get(provider_type)

        if not adapter_class:
            # 尝试使用openai-compatible作为默认
            adapter_class = cls._registry.get("openai-compatible")
            if not adapter_class:
                raise ValueError(f"No adapter found for provider_type='{provider_type}'")

        return adapter_class()

    @classmethod
    def is_supported(cls, provider_type: str, task_type: str) -> bool:
        """
        检查是否支持指定的provider_type和task_type组合。

        Args:
            provider_type: 提供商类型。
            task_type: 任务类型（llm、embedding 或 rerank）。

        Returns:
            是否支持。
        """
        adapter = cls.get_adapter(provider_type)
        
        if task_type == "llm":
            return adapter.supports_llm()
        elif task_type == "embedding":
            return adapter.supports_embedding()
        elif task_type == "rerank":
            return adapter.supports_rerank()
        return False

    @classmethod
    def list_providers(cls) -> list[str]:
        """返回所有已注册的provider类型列表。"""
        return list(cls._registry.keys())

    @classmethod
    def get_supported_task_types(cls, provider_type: str) -> list[str]:
        """
        获取指定provider支持的任务类型列表。

        Args:
            provider_type: 提供商类型。

        Returns:
            支持的任务类型列表（如 ["llm", "embedding", "rerank"]）。
        """
        adapter = cls.get_adapter(provider_type)
        task_types = []
        if adapter.supports_llm():
            task_types.append("llm")
        if adapter.supports_embedding():
            task_types.append("embedding")
        if adapter.supports_rerank():
            task_types.append("rerank")
        return task_types
