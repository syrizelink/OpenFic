# -*- coding: utf-8 -*-
"""
ModelProvider API Tests - Rerank 能力暴露测试。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repos import model_provider_repo


@pytest.mark.asyncio
async def test_openai_provider_exposes_rerank_task_type(
    client: AsyncClient, session: AsyncSession
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test OpenAI",
        url="https://api.openai.com/v1",
        api_key_encrypted=encrypted_key,
        provider_type="openai",
    )
    await session.commit()

    response = await client.get(f"/api/v1/model-providers/{provider.id}")
    assert response.status_code == 200

    data = response.json()
    assert "rerank" in data["supported_task_types"]


@pytest.mark.asyncio
async def test_anthropic_provider_does_not_expose_rerank_task_type(
    client: AsyncClient, session: AsyncSession
):
    from app.core.encryption import EncryptionService
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Anthropic",
        url="https://api.anthropic.com",
        api_key_encrypted=encrypted_key,
        provider_type="anthropic",
    )
    await session.commit()

    response = await client.get(f"/api/v1/model-providers/{provider.id}")
    assert response.status_code == 200

    data = response.json()
    assert "rerank" not in data["supported_task_types"]
