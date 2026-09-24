"""Resolve configured models into LLM clients for background jobs."""

from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.memory.summary_config import (
    SUMMARY_DEFAULT_MODEL_REFERENCE,
    SUMMARY_LIGHT_MODEL_REFERENCE,
    load_summary_settings,
    resolve_summary_model_id,
)
from app.models.clients import LLMClient, LLMConfig
from app.models.clients.model_params import ReasoningEffort, normalize_reasoning_effort
from app.models.entities.model import Model
from app.models.entities.model_provider import ModelProvider
from app.models.repos import model_provider_repo, model_repo
from app.models.services.model_provider_service import ModelProviderService
from app.settings import settings
from app.storage.repos import setting_repo


class BackgroundModelUnavailableError(RuntimeError):
    """Raised when a background model policy cannot resolve a usable model."""


async def _resolve_background_reasoning_effort(
    session: AsyncSession,
    model_policy: str,
) -> ReasoningEffort | None:
    setting_key = {
        "default_model": "default_model_reasoning_effort",
        "light_model": "light_model_reasoning_effort",
    }.get(model_policy)
    if model_policy == "summary_model":
        summary_model_value = (await load_summary_settings(session)).model_id
        if summary_model_value == SUMMARY_DEFAULT_MODEL_REFERENCE:
            setting_key = "default_model_reasoning_effort"
        elif summary_model_value == SUMMARY_LIGHT_MODEL_REFERENCE:
            setting_key = "light_model_reasoning_effort"
        else:
            setting_key = "summary_model_reasoning_effort"
    if setting_key is None:
        return None
    setting = await setting_repo.get_by_key(session, setting_key)
    return normalize_reasoning_effort(setting.value if setting else None)


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
    if not effective_model_id:
        if model_policy == "summary_model":
            effective_model_id = await resolve_summary_model_id(session)
        elif model_policy in {"default_model", "light_model"}:
            setting = await setting_repo.get_by_key(session, model_policy)
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
    custom_headers = ModelProviderService(
        encryption_service
    ).get_decrypted_custom_headers(provider)
    reasoning_effort = await _resolve_background_reasoning_effort(session, model_policy)
    return ResolvedLLM(
        client=LLMClient(
            LLMConfig(
                provider_type=provider.provider_type,
                base_url=provider.url,
                api_key=api_key,
                model_id=model.model_id,
                custom_headers=custom_headers or None,
                temperature=model.temperature,
                top_p=model.top_p,
                top_k=model.top_k,
                min_p=model.min_p,
                top_a=model.top_a,
                max_tokens=model.max_tokens,
                frequency_penalty=model.frequency_penalty,
                presence_penalty=model.presence_penalty,
                repetition_penalty=model.repetition_penalty,
                reasoning_effort=reasoning_effort,
                request_timeout=int(settings.llm_request_timeout),
            )
        ),
        model=model,
        provider=provider,
    )
