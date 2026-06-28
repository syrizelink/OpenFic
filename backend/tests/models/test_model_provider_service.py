# -*- coding: utf-8 -*-
"""
ModelProviderService Tests.
"""

import pytest

from app.core.encryption import EncryptionService
from app.models.entities.model_provider import ModelProvider
from app.models.registry import AdapterRegistry
from app.models.services.model_provider_service import ModelProviderService


class _FakeAdapter:
    @property
    def provider_type(self) -> str:
        return "openai"

    async def get_llm_models(self, client, base_url: str, api_key: str) -> list[dict[str, str]]:
        return [{"id": "llm-1", "name": "LLM 1"}]

    async def get_embedding_models(
        self, client, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return [{"id": "embedding-1", "name": "Embedding 1"}]

    async def get_rerank_models(
        self, client, base_url: str, api_key: str
    ) -> list[dict[str, str]]:
        return [{"id": "rerank-1", "name": "Rerank 1"}]

    def supports_llm(self) -> bool:
        return True

    def supports_embedding(self) -> bool:
        return True

    def supports_rerank(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_get_available_models_routes_rerank_to_rerank_models(monkeypatch):
    encryption_service = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption_service)
    provider = ModelProvider(
        name="Test OpenAI",
        url="https://api.openai.com/v1",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        provider_type="openai",
    )

    monkeypatch.setattr(AdapterRegistry, "get_adapter", classmethod(lambda cls, provider_type: _FakeAdapter()))

    models = await service.get_available_models(provider, "rerank")

    assert models == [{"id": "rerank-1", "name": "Rerank 1"}]
