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
        "openai-codex",
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


def test_model_service_package_exports_match_direct_imports() -> None:
    from app.models import ModelProviderService, ModelService
    from app.models.services import ModelProviderService as ExportedProviderService
    from app.models.services import ModelService as ExportedModelService
    from app.models.services.model_provider_service import ModelProviderService as DirectProviderService
    from app.models.services.model_service import ModelService as DirectModelService

    assert ModelProviderService is ExportedProviderService is DirectProviderService
    assert ModelService is ExportedModelService is DirectModelService
