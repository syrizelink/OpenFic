# -*- coding: utf-8 -*-
"""
ModelProvider API Tests - 模型服务提供商 API 测试。
"""

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repos import model_provider_repo

_OPENAI_ICON_URL = "/icons/model/catalog/openai.svg"
_OPENROUTER_ICON_URL = "/icons/model/catalog/openrouter.svg"


@pytest.mark.asyncio
async def test_create_provider(client: AsyncClient, session: AsyncSession):
    """测试创建提供商。"""
    request_data = {
        "name": "Test OpenAI",
        "url": "https://api.openai.com",
        "api_key": "sk-test-key",
        "provider_type": "openai",
    }

    response = await client.post("/api/v1/model-providers", data=request_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test OpenAI"
    assert data["url"] == "https://api.openai.com"
    assert data["provider_type"] == "openai"
    assert data["catalog_match"]["catalog_provider_type"] == "openai"
    assert data["catalog_match"]["matched_via"] == "provider_type"
    assert data["icon_path"] == _OPENAI_ICON_URL
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_all_providers(client: AsyncClient, session: AsyncSession):
    """测试获取所有提供商。"""
    # 创建测试数据
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    await model_provider_repo.create(
        session=session,
        name="Provider 1",
        url="https://api.example.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    response = await client.get("/api/v1/model-providers")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_provider_by_id(client: AsyncClient, session: AsyncSession):
    """测试根据 ID 获取提供商。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.example.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    response = await client.get(f"/api/v1/model-providers/{provider.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == provider.id
    assert data["name"] == "Test Provider"
    assert data["catalog_match"]["catalog_provider_type"] == "openai"


@pytest.mark.asyncio
async def test_openai_compatible_provider_matches_catalog_by_exact_api_normalization(
    client: AsyncClient, session: AsyncSession
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Compat OpenRouter",
        url="https://openrouter.ai/api/v1/",
        api_key_encrypted=encrypted_key,
        provider_type="openai-compatible",
    )
    await session.commit()

    response = await client.get(f"/api/v1/model-providers/{provider.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["catalog_match"]["catalog_provider_type"] == "openrouter"
    assert data["catalog_match"]["matched_via"] == "api"
    assert data["icon_path"] == _OPENROUTER_ICON_URL


@pytest.mark.asyncio
async def test_openai_compatible_provider_matches_non_default_catalog_provider_by_api(
    client: AsyncClient, session: AsyncSession
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Compat Upstage",
        url="https://api.upstage.ai/v1/solar/",
        api_key_encrypted=encrypted_key,
        provider_type="openai-compatible",
    )
    await session.commit()

    response = await client.get(f"/api/v1/model-providers/{provider.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["catalog_match"]["catalog_provider_type"] == "upstage"
    assert data["catalog_match"]["matched_via"] == "api"
    assert data["catalog_match"]["display_name"] == "Upstage"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_create_provider_ignores_uploaded_icon(
    client: AsyncClient, session: AsyncSession
):
    response = await client.post(
        "/api/v1/model-providers",
        data={
            "name": "OpenAI with uploaded icon",
            "url": "https://api.openai.com/v1",
            "api_key": "sk-test-key",
            "provider_type": "openai",
        },
        files={"icon": ("custom-provider.svg", b"<svg />", "image/svg+xml")},
    )

    assert response.status_code == 201
    assert response.json()["icon_path"] == _OPENAI_ICON_URL


@pytest.mark.asyncio
async def test_update_provider(client: AsyncClient, session: AsyncSession):
    """测试更新提供商。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Old Name",
        url="https://api.example.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    update_data = {"name": "New Name"}
    response = await client.put(
        f"/api/v1/model-providers/{provider.id}", data=update_data
    )
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_provider(client: AsyncClient, session: AsyncSession):
    """测试删除提供商。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="To Delete",
        url="https://api.example.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    response = await client.delete(f"/api/v1/model-providers/{provider.id}")
    assert response.status_code == 204

    # 验证已删除
    deleted_provider = await model_provider_repo.get_by_id(session, provider.id)
    assert deleted_provider is None


@pytest.mark.asyncio
@respx.mock
async def test_validate_provider_invalid_credentials(
    client: AsyncClient, session: AsyncSession
):
    """测试验证提供商连接（无效凭据）。"""
    respx.get("https://api.openai.com/v1/models").mock(
        return_value=httpx.Response(401, json={"error": {"message": "Invalid API key"}})
    )

    request_data = {
        "provider_type": "openai",
        "url": "https://api.openai.com",
        "api_key": "invalid-key",
    }

    response = await client.post("/api/v1/model-providers/validate", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert "message" in data


@pytest.mark.asyncio
async def test_create_openrouter_provider(client: AsyncClient, session: AsyncSession):
    """测试创建 OpenRouter 提供商。"""
    # 使用 FormData 格式（与 API 定义一致）
    form_data = {
        "name": "Test OpenRouter",
        "url": "https://openrouter.ai/api/v1",
        "api_key": "sk-or-test-key",
        "provider_type": "openrouter",
    }

    response = await client.post("/api/v1/model-providers", data=form_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test OpenRouter"
    assert data["url"] == "https://openrouter.ai/api/v1"
    assert data["provider_type"] == "openrouter"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_openrouter_provider_models(
    client: AsyncClient, session: AsyncSession
):
    """测试获取 OpenRouter 提供商的模型列表。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("sk-or-test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test OpenRouter",
        url="https://openrouter.ai/api/v1",
        api_key_encrypted=encrypted_key,
        provider_type="openrouter",
    )
    await session.commit()

    response = await client.get(f"/api/v1/model-providers/{provider.id}/models")
    # 由于是测试环境，可能无法真正连接到 OpenRouter，所以可能返回失败
    # 但至少应该返回正确的响应格式
    assert response.status_code == 200

    data = response.json()
    assert "success" in data
    assert "message" in data
    assert "models" in data
    assert isinstance(data["models"], list)


@pytest.mark.asyncio
async def test_get_provider_models_enriches_remote_models_with_catalog_metadata(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.core.encryption import EncryptionService
    from app.models.services.model_provider_service import ModelProviderService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("sk-deepseek-test-key")

    saved_provider = await model_provider_repo.create(
        session=session,
        name="Test DeepSeek",
        url="https://api.deepseek.com",
        api_key_encrypted=encrypted_key,
        provider_type="deepseek",
    )
    await session.commit()

    async def fake_get_available_models(self, provider, task_type):
        assert provider.id == saved_provider.id
        assert task_type == "llm"
        return [
            {"id": "deepseek-chat", "name": "raw-remote-name"},
            {"id": "deepseek-v4-pro", "name": "another-raw-remote-name"},
            {"id": "custom-remote-model", "name": "Custom Remote Model"},
        ]

    monkeypatch.setattr(
        ModelProviderService,
        "get_available_models",
        fake_get_available_models,
    )

    response = await client.get(f"/api/v1/model-providers/{saved_provider.id}/models")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["models"]) == 3
    assert [model["id"] for model in data["models"]] == [
        "deepseek-v4-pro",
        "deepseek-chat",
        "custom-remote-model",
    ]

    newest_matched_model = next(
        model for model in data["models"] if model["id"] == "deepseek-v4-pro"
    )
    matched_model = next(
        model for model in data["models"] if model["id"] == "deepseek-chat"
    )
    unmatched_model = next(
        model for model in data["models"] if model["id"] == "custom-remote-model"
    )

    assert newest_matched_model["task_type"] == "llm"
    assert newest_matched_model["name"] == "DeepSeek V4 Pro"
    assert newest_matched_model["metadata"]["release_date"] == "2026-04-24"
    assert newest_matched_model["metadata"]["tool_call"] is True
    assert newest_matched_model["metadata"]["cost"]["input"] == 0.435
    assert matched_model["task_type"] == "llm"
    assert matched_model["name"] == "DeepSeek Chat"
    assert matched_model["metadata"]["release_date"] == "2025-12-01"
    assert matched_model["metadata"]["tool_call"] is True
    assert matched_model["metadata"]["limit"]["context"] == 1000000
    assert matched_model["metadata"]["cost"]["input"] == 0.14
    assert matched_model["metadata"]["cost"]["cache_read"] == 0.0028
    assert unmatched_model["task_type"] == "llm"
    assert unmatched_model["name"] == "Custom Remote Model"
    assert unmatched_model["metadata"] is None
