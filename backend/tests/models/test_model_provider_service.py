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


@pytest.mark.asyncio
async def test_get_available_models_uses_openai_compatible_adapter_for_catalog_provider(
    monkeypatch,
):
    encryption_service = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption_service)
    provider = ModelProvider(
        name="Upstage",
        url="https://api.upstage.ai/v1/solar",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        provider_type="upstage",
    )
    requested_provider_types: list[str] = []

    def get_adapter(cls, provider_type: str):
        requested_provider_types.append(provider_type)
        return _FakeAdapter()

    def is_supported(cls, provider_type: str, task_type: str) -> bool:
        requested_provider_types.append(provider_type)
        return True

    monkeypatch.setattr(AdapterRegistry, "get_adapter", classmethod(get_adapter))
    monkeypatch.setattr(AdapterRegistry, "is_supported", classmethod(is_supported))

    models = await service.get_available_models(provider, "llm")

    assert models == [{"id": "llm-1", "name": "LLM 1"}]
    assert requested_provider_types == ["openai-compatible", "openai-compatible"]


@pytest.mark.asyncio
async def test_create_provider_uses_catalog_api_for_directory_provider(monkeypatch):
    encryption_service = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption_service)

    class _CatalogService:
        async def get_provider(self, provider_type: str):
            assert provider_type == "upstage"
            return type(
                "CatalogProvider",
                (),
                {
                    "api": "https://api.upstage.ai",
                    "default_url": "https://api.upstage.ai/v1/solar",
                },
            )()

    captured: dict[str, str] = {}

    async def create(*, session, name, url, api_key_encrypted, provider_type):
        captured["url"] = url
        return ModelProvider(
            name=name,
            url=url,
            api_key_encrypted=api_key_encrypted,
            provider_type=provider_type,
        )

    class _Session:
        async def commit(self) -> None:
            return None

    service.catalog_service = _CatalogService()
    monkeypatch.setattr("app.models.services.model_provider_service.model_provider_repo.create", create)

    await service.create_provider(
        session=_Session(),
        name="Upstage",
        url="https://override.example/v1",
        api_key="test-key",
        provider_type="upstage",
    )

    assert captured["url"] == "https://api.upstage.ai/v1/solar"


@pytest.mark.asyncio
async def test_create_provider_uses_supplied_url_when_directory_provider_lacks_api(
    monkeypatch,
):
    encryption_service = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption_service)

    class _CatalogService:
        async def get_provider(self, provider_type: str):
            assert provider_type == "no-api-provider"
            return type("CatalogProvider", (), {"api": None, "default_url": None})()

    captured: dict[str, str] = {}

    async def create(*, session, name, url, api_key_encrypted, provider_type):
        captured["url"] = url
        return ModelProvider(
            name=name,
            url=url,
            api_key_encrypted=api_key_encrypted,
            provider_type=provider_type,
        )

    class _Session:
        async def commit(self) -> None:
            return None

    service.catalog_service = _CatalogService()
    monkeypatch.setattr("app.models.services.model_provider_service.model_provider_repo.create", create)

    await service.create_provider(
        session=_Session(),
        name="No API",
        url="https://override.example/v1",
        api_key="test-key",
        provider_type="no-api-provider",
    )

    assert captured["url"] == "https://override.example/v1"
