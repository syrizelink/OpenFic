# -*- coding: utf-8 -*-
"""
Adapter Registry - tabel registrasi adapter.

Memilih Adapter yang sesuai berdasarkan provider_type.
"""

from typing import Type

from app.models.adapters.base import BaseAdapter
from app.models.adapters.anthropic import AnthropicAdapter
from app.models.adapters.anthropic_compatible import AnthropicCompatibleAdapter
from app.models.adapters.deepseek import DeepSeekAdapter
from app.models.adapters.gemini_compatible import GeminiCompatibleAdapter
from app.models.adapters.google_genai import GoogleGenAIAdapter
from app.models.adapters.mistral import MistralAdapter
from app.models.adapters.openai import OpenAIAdapter
from app.models.adapters.openai_compat_family import (
    AmazonNovaAdapter,
    CohereAdapter,
    GroqAdapter,
    HuggingFaceAdapter,
    NvidiaAIEndpointsAdapter,
)
from app.models.adapters.openai_compatible import OpenAICompatibleAdapter
from app.models.adapters.openai_responses_compatible import (
    OpenAIResponsesCompatibleAdapter,
)
from app.models.adapters.openrouter import OpenRouterAdapter


class AdapterRegistry:
    """Tabel registrasi adapter, mengelola pemetaan Provider ke Adapter."""

    # Pemetaan adapter: provider_type -> kelas Adapter
    _registry: dict[str, Type[BaseAdapter]] = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "anthropic-compatible": AnthropicCompatibleAdapter,
        "gemini-compatible": GeminiCompatibleAdapter,
        "google-genai": GoogleGenAIAdapter,
        "ollama": OpenAICompatibleAdapter,
        "groq": GroqAdapter,
        "huggingface": HuggingFaceAdapter,
        "deepseek": DeepSeekAdapter,
        "mistral": MistralAdapter,
        "nvidia-ai-endpoints": NvidiaAIEndpointsAdapter,
        "cohere": CohereAdapter,
        "openrouter": OpenRouterAdapter,
        "amazon-nova": AmazonNovaAdapter,
        "openai-compatible": OpenAICompatibleAdapter,
        "openai-compatible-responses": OpenAIResponsesCompatibleAdapter,
    }

    @classmethod
    def get_adapter(cls, provider_type: str) -> BaseAdapter:
        """
        Mengambil instance Adapter yang sesuai berdasarkan provider_type.

        Args:
            provider_type: jenis penyedia (misalnya openai, openrouter, dll).

        Returns:
            Instance Adapter yang sesuai.

        Raises:
            ValueError: jika Adapter yang sesuai tidak ditemukan.
        """
        adapter_class = cls._registry.get(provider_type)

        if not adapter_class:
            # Coba gunakan openai-compatible sebagai default
            adapter_class = cls._registry.get("openai-compatible")
            if not adapter_class:
                raise ValueError(f"No adapter found for provider_type='{provider_type}'")

        return adapter_class()

    @classmethod
    def is_supported(cls, provider_type: str, task_type: str) -> bool:
        """
        Memeriksa apakah kombinasi provider_type dan task_type didukung.

        Args:
            provider_type: jenis penyedia.
            task_type: jenis tugas (llm, embedding, atau rerank).

        Returns:
            Apakah didukung.
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
        """Mengembalikan daftar semua jenis provider yang telah terdaftar."""
        return list(cls._registry.keys())

    @classmethod
    def get_supported_task_types(cls, provider_type: str) -> list[str]:
        """
        Mengambil daftar jenis tugas yang didukung provider tertentu.

        Args:
            provider_type: jenis penyedia.

        Returns:
            Daftar jenis tugas yang didukung (misalnya ["llm", "embedding", "rerank"]).
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
