# -*- coding: utf-8 -*-
"""OpenAI-compatible provider adapters with distinct provider_type values."""

from app.models.adapters.openai_compatible import OpenAICompatibleAdapter


class GroqAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "groq"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False


class HuggingFaceAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "huggingface"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False


class NvidiaAIEndpointsAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "nvidia-ai-endpoints"

    def supports_embedding(self) -> bool:
        return True

    def supports_rerank(self) -> bool:
        return True


class CohereAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "cohere"

    def supports_embedding(self) -> bool:
        return True

    def supports_rerank(self) -> bool:
        return False


class AmazonNovaAdapter(OpenAICompatibleAdapter):
    @property
    def provider_type(self) -> str:
        return "amazon-nova"

    def supports_embedding(self) -> bool:
        return False

    def supports_rerank(self) -> bool:
        return False
