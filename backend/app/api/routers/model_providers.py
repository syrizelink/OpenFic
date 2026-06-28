# -*- coding: utf-8 -*-
"""
ModelProvider Router - 模型服务提供商 API。
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.model_provider import (
    AvailableModel,
    CatalogMatchResponse,
    ModelProviderResponse,
    ModelProviderValidateRequest,
    ModelProviderValidateResponse,
)
from app.models.catalog import ModelProviderCatalogService
from app.core.encryption import EncryptionService
from app.core.errors import NotFoundError
from app.settings import settings
from app.storage.database import get_session
from app.models.services import ModelProviderService

router = APIRouter(prefix="/model-providers", tags=["model-providers"])


def get_encryption_service() -> EncryptionService:
    """获取加密服务实例。"""
    return EncryptionService(settings.encryption_key)


def get_catalog_service() -> ModelProviderCatalogService:
    """获取 catalog 服务实例。"""
    return ModelProviderCatalogService()


def get_provider_service(
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
    catalog_service: Annotated[
        ModelProviderCatalogService, Depends(get_catalog_service)
    ],
) -> ModelProviderService:
    """获取提供商服务实例。"""
    return ModelProviderService(encryption_service, catalog_service)


async def _build_provider_response(
    provider,
    service: ModelProviderService,
) -> ModelProviderResponse:
    catalog_match = await service.get_catalog_match(provider)
    supported_task_types = await service.get_supported_task_types(provider)
    icon_path = await service.get_effective_icon_path(provider)

    return ModelProviderResponse(
        id=provider.id,
        name=provider.name,
        url=provider.url,
        provider_type=provider.provider_type,
        supported_task_types=supported_task_types,
        icon_path=icon_path,
        is_builtin=provider.is_builtin,
        catalog_match=(
            CatalogMatchResponse.model_validate(catalog_match.model_dump())
            if catalog_match is not None
            else None
        ),
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[ModelProviderResponse],
    summary="获取所有提供商",
)
async def get_providers(
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> list[ModelProviderResponse]:
    """
    获取所有模型服务提供商。

    Args:
        session: 数据库 session。
        service: 提供商服务。

    Returns:
        提供商列表。
    """
    providers = await service.get_all_providers(session)
    return [await _build_provider_response(provider, service) for provider in providers]


@router.get(
    "/{provider_id}",
    response_model=ModelProviderResponse,
    summary="获取提供商",
)
async def get_provider(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> ModelProviderResponse:
    """
    根据 ID 获取提供商。

    Args:
        provider_id: 提供商 ID。
        session: 数据库 session。
        service: 提供商服务。

    Returns:
        提供商信息。

    Raises:
        HTTPException: 如果提供商不存在。
    """
    try:
        provider = await service.get_provider_by_id(session, provider_id)
        return await _build_provider_response(provider, service)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "",
    response_model=ModelProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建提供商",
)
async def create_provider(
    url: Annotated[str, Form()],
    provider_type: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    api_key: Annotated[str | None, Form()] = None,
    icon: Annotated[UploadFile | None, File()] = None,
    session: AsyncSession = Depends(get_session),
    service: ModelProviderService = Depends(get_provider_service),
) -> ModelProviderResponse:
    """
    创建模型服务提供商。

    Args:
        name: 提供商名称/备注。
        url: 服务 URL。
        api_key: API Key。
        provider_type: 提供商类型。
        icon: 图标文件。
        session: 数据库 session。
        service: 提供商服务。

    Returns:
        创建的提供商信息。
    """
    logger.info(f"创建提供商: {provider_type}")

    provider = await service.create_provider(
        session=session,
        name=name,
        url=url,
        api_key=api_key or "",
        provider_type=provider_type,
        icon_file=icon,
    )

    return await _build_provider_response(provider, service)


@router.put(
    "/{provider_id}",
    response_model=ModelProviderResponse,
    summary="更新提供商",
)
async def update_provider(
    provider_id: str,
    name: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    api_key: Annotated[str | None, Form()] = None,
    provider_type: Annotated[str | None, Form()] = None,
    icon: Annotated[UploadFile | None, File()] = None,
    session: AsyncSession = Depends(get_session),
    service: ModelProviderService = Depends(get_provider_service),
) -> ModelProviderResponse:
    """
    更新提供商信息。

    Args:
        provider_id: 提供商 ID。
        name: 提供商名称/备注。
        url: 服务 URL。
        api_key: API Key。
        provider_type: 提供商类型。
        icon: 图标文件。
        session: 数据库 session。
        service: 提供商服务。

    Returns:
        更新后的提供商信息。

    Raises:
        HTTPException: 如果提供商不存在。
    """
    logger.info(f"更新提供商: {provider_id}")

    try:
        provider = await service.update_provider(
            session=session,
            provider_id=provider_id,
            name=name,
            url=url,
            api_key=api_key,
            provider_type=provider_type,
            icon_file=icon,
        )

        return await _build_provider_response(provider, service)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除提供商",
)
async def delete_provider(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> None:
    """
    删除提供商。

    Args:
        provider_id: 提供商 ID。
        session: 数据库 session。
        service: 提供商服务。

    Raises:
        HTTPException: 如果提供商不存在。
    """
    logger.info(f"删除提供商: {provider_id}")

    try:
        await service.delete_provider(session, provider_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/validate",
    response_model=ModelProviderValidateResponse,
    summary="验证提供商连接",
)
async def validate_provider(
    request: ModelProviderValidateRequest,
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> ModelProviderValidateResponse:
    """
    验证提供商连接并获取可用模型列表。

    Args:
        request: 验证请求。
        service: 提供商服务。

    Returns:
        验证结果和可用模型列表。
    """
    logger.info(f"验证提供商连接: {request.provider_type}")

    try:
        models = await service.validate_and_get_models(
            provider_type=request.provider_type,
            url=request.url,
            api_key=request.api_key,
        )
        return ModelProviderValidateResponse(
            success=True,
            message="连接验证成功"
            if models
            else "连接验证成功，但该提供商可能不支持模型列表 API",
            models=[
                AvailableModel(
                    id=m["id"],
                    name=m["name"],
                )
                for m in models
            ],
        )
    except Exception as e:
        logger.error(f"验证提供商连接失败: {e}")
        return ModelProviderValidateResponse(
            success=False,
            message=f"连接验证失败: {str(e)}",
            models=[],
        )


@router.get(
    "/{provider_id}/models",
    response_model=ModelProviderValidateResponse,
    summary="获取提供商的模型列表",
)
async def get_provider_models(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
    task_type: str = Query("llm", description="任务类型 (llm、embedding 或 rerank)"),
) -> ModelProviderValidateResponse:
    """
    获取提供商的模型列表。

    Args:
        provider_id: 提供商 ID。
        session: 数据库 session。
        service: 提供商服务。

    Returns:
        模型列表。

    Raises:
        HTTPException: 如果提供商不存在。
    """
    logger.info(f"获取提供商模型列表: {provider_id}")

    try:
        # 获取提供商信息
        provider = await service.get_provider_by_id(session, provider_id)

        # 内置提供商无需 API Key，直接返回固定模型列表
        if provider.is_builtin:
            models = await service.get_available_models(
                provider=provider,
                task_type=task_type,
            )
            enriched_models = await service.enrich_models_with_catalog_metadata(
                provider=provider,
                task_type=task_type,
                models=models,
            )
            return ModelProviderValidateResponse(
                success=True,
                message="获取模型列表成功",
                models=[AvailableModel.model_validate(model) for model in enriched_models],
            )

        # 获取解密后的 API Key
        api_key = service.get_decrypted_api_key(provider)
        if not api_key:
            # 检查是字段为空还是解密失败
            has_encrypted_field = (
                provider.api_key_encrypted and provider.api_key_encrypted.strip() != ""
            )
            if has_encrypted_field:
                logger.warning(
                    f"Provider {provider_id} has encrypted API key but decryption failed. "
                    f"Field length: {len(provider.api_key_encrypted)}"
                )
                return ModelProviderValidateResponse(
                    success=False,
                    message="API Key 解密失败，请重新配置该提供商的 API Key",
                    models=[],
                )
            else:
                logger.info(f"Provider {provider_id} has no API key configured")
                return ModelProviderValidateResponse(
                    success=False,
                    message="该提供商未配置 API Key，无法获取模型列表",
                    models=[],
                )

        # 记录API key的前缀和后缀用于调试（隐藏中间部分）
        if len(api_key) > 8:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        else:
            masked_key = "****"
        logger.debug(f"Using API key: {masked_key} (length: {len(api_key)})")

        # 获取模型列表（根据task_type获取LLM或Embedding模型）
        models = await service.get_available_models(
            provider=provider,
            task_type=task_type,
        )
        enriched_models = await service.enrich_models_with_catalog_metadata(
            provider=provider,
            task_type=task_type,
            models=models,
        )

        logger.info(f"成功获取 {len(models)} 个模型")
        return ModelProviderValidateResponse(
            success=True,
            message="获取模型列表成功" if models else "该提供商可能不支持模型列表 API",
            models=[AvailableModel.model_validate(model) for model in enriched_models],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        # 使用 loguru 的参数化日志记录，避免 error_msg 中的花括号被误认为格式化占位符
        logger.error("获取模型列表失败: {}", error_msg, exc_info=True)
        return ModelProviderValidateResponse(
            success=False,
            message=f"获取模型列表失败: {error_msg}",
            models=[],
        )
