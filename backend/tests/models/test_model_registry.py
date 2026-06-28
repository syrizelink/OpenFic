# -*- coding: utf-8 -*-
"""
Adapter registry tests.
"""

from app.models.registry import AdapterRegistry


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
        "amazon-nova",
        "deepseek",
        "openai-compatible",
    }
    assert "google-vertex" not in AdapterRegistry.list_providers()
