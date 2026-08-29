# -*- coding: utf-8 -*-
"""
Model API Tests - 模型 API 测试。
"""

import json

import pytest
import respx
from httpx import Response
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
        "input_price": 2.0,
        "output_price": 8.0,
        "cache_read_price": 0.5,
        "cache_write_price": 1.0,
    }

    response = await client.post("/api/v1/models", json=request_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "GPT-4"
    assert data["model_id"] == "gpt-4"
    assert data["temperature"] == 0.7
    assert data["input_price"] == 2.0
    assert data["output_price"] == 8.0
    assert data["cache_read_price"] == 0.5
    assert data["cache_write_price"] == 1.0
    assert "tags" not in data


@pytest.mark.asyncio
@respx.mock
async def test_validate_model_connection_sends_non_streaming_probe(
    client: AsyncClient, session: AsyncSession
):
    """验证模型连接时只发送一条非流式 user probe 消息。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Validation Provider",
        url="https://api.example.com/v1",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
        provider_type="openai",
    )
    model = await model_repo.create(
        session=session,
        name="Validation Model",
        provider_id=provider.id,
        model_id="validation-model",
    )
    await session.commit()

    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-validation",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )

    response = await client.post(f"/api/v1/models/{model.id}/validate")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "模型连接验证成功"}
    request_body = route.calls[0].request.content
    assert request_body
    payload = json.loads(request_body)
    assert payload["model"] == "validation-model"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert payload["stream"] is False


@pytest.mark.asyncio
@respx.mock
async def test_validate_model_connection_reports_failed_provider_request(
    client: AsyncClient, session: AsyncSession
):
    """提供商请求失败时，模型验证返回失败状态。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    provider = await model_provider_repo.create(
        session=session,
        name="Failed Validation Provider",
        url="https://api.example.com/v1",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
        provider_type="openai",
    )
    model = await model_repo.create(
        session=session,
        name="Failed Validation Model",
        provider_id=provider.id,
        model_id="failed-validation-model",
    )
    await session.commit()

    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=Response(401, json={"error": {"message": "Invalid API key"}})
    )

    response = await client.post(f"/api/v1/models/{model.id}/validate")

    assert response.status_code == 200
    assert response.json() == {"success": False, "message": "模型连接验证失败"}


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
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
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
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
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
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
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
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
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
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
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
