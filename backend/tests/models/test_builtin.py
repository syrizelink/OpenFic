# -*- coding: utf-8 -*-
"""
Builtin models tests - 内置 fastembed 模型的 seeding 与保护逻辑。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.builtin import (
    BUILTIN_EMBEDDING_MODEL_ID,
    BUILTIN_EMBEDDING_MODEL_NAME,
    BUILTIN_PROVIDER_ID,
    BUILTIN_PROVIDER_TYPE,
    BUILTIN_RERANK_MODEL_ID,
    BUILTIN_RERANK_MODEL_NAME,
    seed_builtin_models,
)
from app.models.entities.model import Model
from app.models.repos import model_repo, model_provider_repo
from app.models.services.model_provider_service import ModelProviderService
from sqlalchemy import select
from sqlmodel import col


@pytest.mark.asyncio
async def test_seed_builtin_models_creates_provider_and_models(
    session: AsyncSession,
):
    await seed_builtin_models(session)

    provider = await model_provider_repo.get_by_id(session, BUILTIN_PROVIDER_ID)
    assert provider is not None
    assert provider.is_builtin is True
    assert provider.provider_type == BUILTIN_PROVIDER_TYPE

    embedding = await model_repo.get_by_id(session, BUILTIN_EMBEDDING_MODEL_ID)
    assert embedding is not None
    assert embedding.is_builtin is True
    assert embedding.task_type == "embedding"
    assert embedding.name == BUILTIN_EMBEDDING_MODEL_NAME
    assert embedding.dimensions == 512

    rerank = await model_repo.get_by_id(session, BUILTIN_RERANK_MODEL_ID)
    assert rerank is not None
    assert rerank.is_builtin is True
    assert rerank.task_type == "rerank"
    assert rerank.name == BUILTIN_RERANK_MODEL_NAME


@pytest.mark.asyncio
async def test_seed_builtin_models_is_idempotent(session: AsyncSession):
    await seed_builtin_models(session)
    await seed_builtin_models(session)

    result = await session.execute(
        select(Model).where(col(Model.provider_id) == BUILTIN_PROVIDER_ID)
    )
    models = list(result.scalars().all())
    assert len(models) == 2


@pytest.mark.asyncio
async def test_delete_builtin_model_is_blocked(
    client: AsyncClient, session: AsyncSession
):
    await seed_builtin_models(session)
    await session.commit()

    response = await client.delete(f"/api/v1/models/{BUILTIN_EMBEDDING_MODEL_ID}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_builtin_model_is_blocked(
    client: AsyncClient, session: AsyncSession
):
    await seed_builtin_models(session)
    await session.commit()

    response = await client.put(
        f"/api/v1/models/{BUILTIN_RERANK_MODEL_ID}",
        json={"name": "renamed"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_builtin_provider_is_blocked(
    client: AsyncClient, session: AsyncSession
):
    await seed_builtin_models(session)
    await session.commit()

    response = await client.delete(f"/api/v1/model-providers/{BUILTIN_PROVIDER_ID}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_builtin_provider_supported_task_types(session: AsyncSession):
    from app.core.encryption import EncryptionService

    await seed_builtin_models(session)
    provider = await model_provider_repo.get_by_id(session, BUILTIN_PROVIDER_ID)
    assert provider is not None

    service = ModelProviderService(EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ="))
    task_types = await service.get_supported_task_types(provider)
    assert task_types == ["embedding", "rerank"]


@pytest.mark.asyncio
async def test_builtin_provider_models_endpoint(
    client: AsyncClient, session: AsyncSession
):
    await seed_builtin_models(session)
    await session.commit()

    response = await client.get(
        f"/api/v1/model-providers/{BUILTIN_PROVIDER_ID}/models",
        params={"task_type": "embedding"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["models"]) == 1
    assert data["models"][0]["id"] == "BAAI/bge-small-zh-v1.5"


@pytest.mark.asyncio
async def test_list_models_includes_builtin_flag(
    client: AsyncClient, session: AsyncSession
):
    await seed_builtin_models(session)
    await session.commit()

    response = await client.get("/api/v1/models", params={"task_type": "embedding"})
    assert response.status_code == 200
    models = response.json()
    builtin = [m for m in models if m.get("is_builtin")]
    assert len(builtin) == 1
    assert builtin[0]["id"] == BUILTIN_EMBEDDING_MODEL_ID
