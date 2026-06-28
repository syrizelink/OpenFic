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
        "tags": ["test", "gpt"],
        "temperature": 0.7,
    }

    response = await client.post("/api/v1/models", json=request_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "GPT-4"
    assert data["model_id"] == "gpt-4"
    assert data["temperature"] == 0.7
    assert "test" in data["tags"]


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


@pytest.mark.asyncio
async def test_get_all_tags(client: AsyncClient, session: AsyncSession):
    """测试获取所有标签。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings
    import json

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
        tags=json.dumps(["tag1", "tag2"]),
    )
    await model_repo.create(
        session=session,
        name="Model 2",
        provider_id=provider.id,
        model_id="model-2",
        tags=json.dumps(["tag2", "tag3"]),
    )
    await session.commit()

    response = await client.get("/api/v1/models/tags")
    assert response.status_code == 200

    data = response.json()
    assert "tags" in data
    assert "tag1" in data["tags"]
    assert "tag2" in data["tags"]
    assert "tag3" in data["tags"]
