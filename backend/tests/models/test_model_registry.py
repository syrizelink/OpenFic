# -*- coding: utf-8 -*-
"""
Adapter registry tests.
"""

from app.models.registry import AdapterRegistry
from app.models.adapters.anthropic_compatible import AnthropicCompatibleAdapter


_ANTHROPIC_COMPATIBLE_PROVIDER_TYPES = {
    "freemodel",
    "minimax",
    "minimax-cn",
    "minimax-coding-plan",
    "minimax-cn-coding-plan",
    "subconscious",
    "thinkingmachines",
}


def test_registry_lists_only_current_first_class_provider_types() -> None:
    assert set(AdapterRegistry.list_providers()) == {
        "openai",
        "anthropic",
        "google-genai",
        "ollama",
        "groq",
        "huggingface",
        "mistral",
        "nvidia-ai-endpoints",
        "cohere",
        "openrouter",
        "requesty",
        "amazon-nova",
        "deepseek",
        "openai-compatible",
        "openai-compatible-responses",
        "anthropic-compatible",
        "gemini-compatible",
        *_ANTHROPIC_COMPATIBLE_PROVIDER_TYPES,
    }
    assert "google-vertex" not in AdapterRegistry.list_providers()


def test_registry_uses_anthropic_compatible_adapter_for_anthropic_catalog_providers() -> None:
    for provider_type in _ANTHROPIC_COMPATIBLE_PROVIDER_TYPES:
        adapter = AdapterRegistry.get_adapter(provider_type)

        assert isinstance(adapter, AnthropicCompatibleAdapter)
