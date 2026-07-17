# -*- coding: utf-8 -*-
"""
Model API Tests - 模型 API 测试。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repos import model_provider_repo, model_repo


@pytest.mark.asyncio
async def test_create_model(client: AsyncClient, session: AsyncSession):
    """测试创建模型。"""
    # 先创建提供商
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

    request_data = {
        "name": "GPT-4",
        "provider_id": provider.id,
        "model_id": "gpt-4",
        "remark": "Test model",
        "temperature": 0.7,
    }

    response = await client.post("/api/v1/models", json=request_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "GPT-4"
    assert data["model_id"] == "gpt-4"
    assert data["temperature"] == 0.7
    assert "tags" not in data


@pytest.mark.asyncio
async def test_create_model_rejects_duplicate_name(
    client: AsyncClient, session: AsyncSession
):
    """创建模型时拒绝与已有模型同名的名称。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.example.com",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt("test-key"),
        provider_type="openai",
    )
    await model_repo.create(
        session=session,
        name="GPT-4",
        provider_id=provider.id,
        model_id="gpt-4",
    )
    await session.commit()

    response = await client.post(
        "/api/v1/models",
        json={
            "name": "GPT-4",
            "provider_id": provider.id,
            "model_id": "gpt-4o",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "模型名称已存在"


@pytest.mark.asyncio
async def test_create_model_uses_normalized_advanced_parameter_defaults(
    client: AsyncClient, session: AsyncSession
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.example.com",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt("test-key"),
        provider_type="openai",
    )
    await session.commit()

    response = await client.post(
        "/api/v1/models",
        json={
            "name": "Default Model",
            "provider_id": provider.id,
            "model_id": "gpt-4o",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["temperature"] == 1.0
    assert data["top_p"] == 1.0
    assert data["top_k"] == 0
    assert data["frequency_penalty"] == 0.0
    assert data["presence_penalty"] == 0.0
    assert data["repetition_penalty"] == 1.0
    assert data["min_p"] == 0.0
    assert data["top_a"] == 0.0
    assert data["context_length"] == 128000


@pytest.mark.asyncio
async def test_create_model_rejects_context_length_above_two_million(
    client: AsyncClient, session: AsyncSession
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.example.com",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt("test-key"),
        provider_type="openai",
    )
    await session.commit()

    response = await client.post(
        "/api/v1/models",
        json={
            "name": "Oversized Context Model",
            "provider_id": provider.id,
            "model_id": "gpt-4o",
            "context_length": 2000001,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_all_models(client: AsyncClient, session: AsyncSession):
    """测试获取所有模型。"""
    # 创建测试数据
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

    await model_repo.create(
        session=session,
        name="Test Model",
        provider_id=provider.id,
        model_id="test-model",
    )
    await session.commit()

    response = await client.get("/api/v1/models")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_find_legacy_agent_model_requires_a_unique_match(
    client: AsyncClient,
    session: AsyncSession,
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encrypted_key = EncryptionService(settings.encryption_key).encrypt("test-key")
    provider = await model_provider_repo.create(
        session=session,
        name="Legacy Provider",
        url="https://api.example.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai-compatible",
    )
    first_model = await model_repo.create(
        session=session,
        name="Legacy Model 1",
        provider_id=provider.id,
        model_id="legacy-model",
    )
    await session.commit()

    matched = await model_repo.get_by_legacy_agent_config(
        session,
        model_id="legacy-model",
        provider_type="openai-compatible",
        base_url="https://api.example.com",
    )

    assert matched is not None
    assert matched.id == first_model.id

    await model_repo.create(
        session=session,
        name="Legacy Model 2",
        provider_id=provider.id,
        model_id="legacy-model",
    )
    await session.commit()

    ambiguous_match = await model_repo.get_by_legacy_agent_config(
        session,
        model_id="legacy-model",
        provider_type="openai-compatible",
        base_url="https://api.example.com",
    )

    assert ambiguous_match is None


@pytest.mark.asyncio
async def test_get_models_by_provider(client: AsyncClient, session: AsyncSession):
    """测试根据提供商 ID 获取模型。"""
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

    await model_repo.create(
        session=session,
        name="Model 1",
        provider_id=provider.id,
        model_id="model-1",
    )
    await model_repo.create(
        session=session,
        name="Model 2",
        provider_id=provider.id,
        model_id="model-2",
    )
    await session.commit()

    response = await client.get(f"/api/v1/models?provider_id={provider.id}")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_model(client: AsyncClient, session: AsyncSession):
    """测试更新模型。"""
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

    model = await model_repo.create(
        session=session,
        name="Old Name",
        provider_id=provider.id,
        model_id="test-model",
    )
    await session.commit()

    update_data = {"name": "New Name", "temperature": 0.8}
    response = await client.put(f"/api/v1/models/{model.id}", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "New Name"
    assert data["temperature"] == 0.8


@pytest.mark.asyncio
async def test_update_model_rejects_duplicate_name(
    client: AsyncClient, session: AsyncSession
):
    """编辑模型时拒绝与其他模型同名的名称。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.example.com",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt("test-key"),
        provider_type="openai",
    )
    existing_model = await model_repo.create(
        session=session,
        name="Existing Model",
        provider_id=provider.id,
        model_id="existing-model",
    )
    target_model = await model_repo.create(
        session=session,
        name="Target Model",
        provider_id=provider.id,
        model_id="target-model",
    )
    await session.commit()

    response = await client.put(
        f"/api/v1/models/{target_model.id}",
        json={"name": existing_model.name},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "模型名称已存在"


@pytest.mark.asyncio
async def test_update_model_allows_its_existing_name(
    client: AsyncClient, session: AsyncSession
):
    """编辑模型时允许保留自身原有名称。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.example.com",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt("test-key"),
        provider_type="openai",
    )
    model = await model_repo.create(
        session=session,
        name="Existing Model",
        provider_id=provider.id,
        model_id="existing-model",
    )
    await session.commit()

    response = await client.put(
        f"/api/v1/models/{model.id}",
        json={"name": model.name, "remark": "Updated remark"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == model.name


@pytest.mark.asyncio
async def test_delete_model(client: AsyncClient, session: AsyncSession):
    """测试删除模型。"""
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

    model = await model_repo.create(
        session=session,
        name="To Delete",
        provider_id=provider.id,
        model_id="test-model",
    )
    await session.commit()

    response = await client.delete(f"/api/v1/models/{model.id}")
    assert response.status_code == 204

    # 验证已删除
    deleted_model = await model_repo.get_by_id(session, model.id)
    assert deleted_model is None


