"""Read the default embedding dimensions for a model form selection."""

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.core.errors import NotFoundError
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.repos import model_provider_repo
from app.models.services.model_provider_service import ModelProviderService
from app.settings import settings


async def probe_provider_embedding_dimensions(
    session: AsyncSession, provider_id: str, model_id: str
) -> int:
    """Make one embedding request without saving or modifying a model."""
    provider = await model_provider_repo.get_by_id(session, provider_id)
    if provider is None:
        raise NotFoundError("模型提供商不存在")
    service = ModelProviderService(EncryptionService(settings.encryption_key))
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type=provider.provider_type,
            base_url=provider.url,
            api_key=service.get_decrypted_api_key(provider) or "",
            model_id=model_id,
            custom_headers=service.get_decrypted_custom_headers(provider) or None,
        )
    )
    vector = await client.embed_single("OpenFic embedding dimension check")
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError("嵌入模型返回了空向量或无效向量，无法获取维度")
    return len(vector)
