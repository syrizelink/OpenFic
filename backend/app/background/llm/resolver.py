"""Resolve configured models into LLM clients for background jobs."""

from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.models.clients import LLMClient, LLMConfig
from app.models.entities.model import Model
from app.models.entities.model_provider import ModelProvider
from app.models.repos import model_provider_repo, model_repo
from app.settings import settings
from app.storage.repos import setting_repo


class BackgroundModelUnavailableError(RuntimeError):
    """Raised when a background model policy cannot resolve a usable model."""


@dataclass(frozen=True)
class ResolvedLLM:
    client: LLMClient
    model: Model
    provider: ModelProvider


async def resolve_background_llm(
    session: AsyncSession,
    *,
    model_policy: str,
    model_id: str | None = None,
) -> ResolvedLLM:
    """Resolve a background model policy to an LLM client."""
    effective_model_id = model_id
    if not effective_model_id and model_policy == "light_model":
        setting = await setting_repo.get_by_key(session, "light_model")
        effective_model_id = setting.value.strip() if setting and setting.value else ""

    if not effective_model_id:
        logger.warning(f"后台任务模型未配置，model_policy={model_policy}")
        raise BackgroundModelUnavailableError(f"后台任务模型未配置: {model_policy}")

    model = await model_repo.get_by_id(session, effective_model_id)
    if model is None:
        logger.warning(f"后台任务模型不存在: {effective_model_id}")
        raise BackgroundModelUnavailableError(f"模型不存在: {effective_model_id}")

    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        logger.warning(f"后台任务模型提供商不存在: {model.provider_id}")
        raise BackgroundModelUnavailableError(f"模型提供商不存在: {model.provider_id}")

    encryption_service = EncryptionService(settings.encryption_key)
    api_key = encryption_service.decrypt(provider.api_key_encrypted)
    return ResolvedLLM(
        client=LLMClient(
            LLMConfig(
                provider_type=provider.provider_type,
                base_url=provider.url,
                api_key=api_key,
                model_id=model.model_id,
                temperature=model.temperature,
                top_p=model.top_p,
                top_k=model.top_k,
                min_p=model.min_p,
                top_a=model.top_a,
                max_tokens=model.max_tokens,
                frequency_penalty=model.frequency_penalty,
                presence_penalty=model.presence_penalty,
                repetition_penalty=model.repetition_penalty,
                request_timeout=60,
            )
        ),
        model=model,
        provider=provider,
    )
