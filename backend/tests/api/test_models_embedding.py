# -*- coding: utf-8 -*-
"""
Tests for Model API endpoints - Embedding支持测试。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repos import model_provider_repo, model_repo
from app.retrieval.service import OpenFicRetrievalService
from app.retrieval.types import RetrievalIndexContract


@pytest.mark.asyncio
async def test_create_embedding_model(client: AsyncClient, session: AsyncSession):
    """测试创建Embedding模型。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.test.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    payload = {
        "name": "New Embedding Model",
        "provider_id": provider.id,
        "model_id": "text-embedding-3-large",
        "task_type": "embedding",
        "dimensions": 3072,
    }
    response = await client.post("/api/v1/models", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Embedding Model"
    assert data["task_type"] == "embedding"
    assert data["dimensions"] == 3072
    assert "encoding_format" not in data
    assert data["temperature"] is None


@pytest.mark.asyncio
async def test_create_llm_model_with_task_type(
    client: AsyncClient, session: AsyncSession
):
    """测试创建LLM模型（显式指定task_type）。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.test.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    payload = {
        "name": "New LLM Model",
        "provider_id": provider.id,
        "model_id": "gpt-4-turbo",
        "task_type": "llm",
        "temperature": 0.8,
        "max_tokens": 4000,
    }
    response = await client.post("/api/v1/models", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New LLM Model"
    assert data["task_type"] == "llm"
    assert data["temperature"] == 0.8
    assert data["dimensions"] is None
    assert "encoding_format" not in data


@pytest.mark.asyncio
async def test_create_rerank_model(client: AsyncClient, session: AsyncSession):
    """测试创建 Rerank 模型。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.test.com",
        api_key_encrypted=encrypted_key,
        provider_type="openrouter",
    )
    await session.commit()

    payload = {
        "name": "New Rerank Model",
        "provider_id": provider.id,
        "model_id": "cohere/rerank-3.5",
        "task_type": "rerank",
    }
    response = await client.post("/api/v1/models", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Rerank Model"
    assert data["task_type"] == "rerank"
    assert data["temperature"] is None
    assert data["dimensions"] is None
    assert "encoding_format" not in data


@pytest.mark.asyncio
async def test_get_models_by_task_type(client: AsyncClient, session: AsyncSession):
    """测试按task_type过滤模型。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.test.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )

    # 创建LLM模型
    await model_repo.create(
        session=session,
        name="Test LLM Model",
        provider_id=provider.id,
        model_id="gpt-4",
        task_type="llm",
        temperature=0.7,
    )

    # 创建Embedding模型
    await model_repo.create(
        session=session,
        name="Test Embedding Model",
        provider_id=provider.id,
        model_id="text-embedding-3-small",
        task_type="embedding",
        dimensions=1536,
    )

    # 创建 Rerank 模型
    await model_repo.create(
        session=session,
        name="Test Rerank Model",
        provider_id=provider.id,
        model_id="cohere/rerank-3.5",
        task_type="rerank",
    )
    await session.commit()

    # 测试获取所有模型
    response = await client.get("/api/v1/models")
    assert response.status_code == 200
    all_models = response.json()
    assert len(all_models) == 3

    # 测试只获取LLM模型
    response = await client.get("/api/v1/models?task_type=llm")
    assert response.status_code == 200
    llm_models = response.json()
    assert len(llm_models) == 1
    assert llm_models[0]["task_type"] == "llm"

    # 测试只获取Embedding模型
    response = await client.get("/api/v1/models?task_type=embedding")
    assert response.status_code == 200
    embedding_models = response.json()
    assert len(embedding_models) == 1
    assert embedding_models[0]["task_type"] == "embedding"
    assert embedding_models[0]["dimensions"] == 1536

    response = await client.get("/api/v1/models?task_type=rerank")
    assert response.status_code == 200
    rerank_models = response.json()
    assert len(rerank_models) == 1
    assert rerank_models[0]["task_type"] == "rerank"
    assert rerank_models[0]["model_id"] == "cohere/rerank-3.5"


@pytest.mark.asyncio
async def test_update_model_to_embedding(client: AsyncClient, session: AsyncSession):
    """测试将LLM模型更新为Embedding模型。"""
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.test.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )

    model = await model_repo.create(
        session=session,
        name="Test Model",
        provider_id=provider.id,
        model_id="test-model",
        task_type="llm",
    )
    await session.commit()

    # 更新为embedding类型
    payload = {
        "task_type": "embedding",
        "dimensions": 1024,
    }
    response = await client.put(f"/api/v1/models/{model.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["task_type"] == "embedding"
    assert data["dimensions"] == 1024
    assert "encoding_format" not in data


@pytest.mark.asyncio
async def test_update_bound_embedding_model_dimensions_is_forbidden(
    client: AsyncClient, session: AsyncSession, tmp_path
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://api.test.com",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )

    model = await model_repo.create(
        session=session,
        name="Bound Embedding Model",
        provider_id=provider.id,
        model_id="text-embedding-3-small",
        task_type="embedding",
        dimensions=1536,
    )
    await session.commit()

    retrieval = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    await retrieval.register_index(
        session,
        "bound-index",
        RetrievalIndexContract(
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot="text-embedding-3-small",
            embedding_dimensions_snapshot=1536,
            distance_metric="cosine",
            chunker_type="recursive_character",
            chunk_size=128,
            chunk_overlap=16,
            filterable_fields=[],
            vector_index_type="ivf_hnsw_sq",
            vector_index_params={},
            fts_index_params={},
            schema_version=1,
        ),
    )
    await session.commit()

    response = await client.put(
        f"/api/v1/models/{model.id}",
        json={"dimensions": 3072},
    )

    assert response.status_code == 400
    assert "bound to retrieval indexes" in response.json()["detail"]
