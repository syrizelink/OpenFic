# -*- coding: utf-8 -*-
"""
Model Router - 模型 API。
"""

import json
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.model import (
    ModelCreateRequest,
    ModelResponse,
    ModelUpdateRequest,
    TaskType,
    TagsResponse,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.models.services import ModelService

router = APIRouter(prefix="/models", tags=["models"])
_SUPPORTED_TASK_TYPES = frozenset({"llm", "embedding", "rerank"})


def get_model_service() -> ModelService:
    """获取模型服务实例。"""
    return ModelService()


def _require_task_type(task_type: str) -> TaskType:
    if task_type not in _SUPPORTED_TASK_TYPES:
        raise ValueError(f"Unsupported task_type: {task_type}")
    return cast(TaskType, task_type)


def _to_response(m) -> ModelResponse:
    return ModelResponse(
        id=m.id,
        name=m.name,
        remark=m.remark,
        provider_id=m.provider_id,
        model_id=m.model_id,
        task_type=_require_task_type(m.task_type),
        tags=json.loads(m.tags),
        temperature=m.temperature,
        top_p=m.top_p,
        top_k=m.top_k,
        min_p=m.min_p,
        top_a=m.top_a,
        frequency_penalty=m.frequency_penalty,
        presence_penalty=m.presence_penalty,
        repetition_penalty=m.repetition_penalty,
        max_tokens=m.max_tokens,
        context_length=m.context_length,
        deepseek_reasoning_effort=m.deepseek_reasoning_effort,
        deepseek_thinking_type=m.deepseek_thinking_type,
        dimensions=m.dimensions,
        is_builtin=m.is_builtin,
        created_at=m.created_at.isoformat(),
        updated_at=m.updated_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[ModelResponse],
    summary="获取所有模型",
)
async def get_models(
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
    provider_id: str | None = None,
    task_type: str | None = None,
) -> list[ModelResponse]:
    """
    获取所有模型或按条件过滤。

    Args:
        session: 数据库 session。
        service: 模型服务。
        provider_id: 可选的提供商 ID 过滤。
        task_type: 可选的任务类型过滤（llm 或 embedding）。

    Returns:
        模型列表。
    """
    if provider_id:
        models = await service.get_models_by_provider(session, provider_id, task_type)
    else:
        all_models = await service.get_all_models(session)
        # 如果指定task_type，进行过滤
        if task_type:
            models = [m for m in all_models if m.task_type == task_type]
        else:
            models = all_models

    return [_to_response(m) for m in models]


@router.get(
    "/tags",
    response_model=TagsResponse,
    summary="获取所有标签",
)
async def get_tags(
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> TagsResponse:
    """
    获取所有已使用的标签。

    Args:
        session: 数据库 session。
        service: 模型服务。

    Returns:
        标签列表。
    """
    tags = await service.get_all_tags(session)
    return TagsResponse(tags=tags)


@router.get(
    "/{model_id}",
    response_model=ModelResponse,
    summary="获取模型",
)
async def get_model(
    model_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    """
    根据 ID 获取模型。

    Args:
        model_id: 模型 ID。
        session: 数据库 session。
        service: 模型服务。

    Returns:
        模型信息。

    Raises:
        HTTPException: 如果模型不存在。
    """
    try:
        model = await service.get_model_by_id(session, model_id)
        return _to_response(model)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "",
    response_model=ModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建模型",
)
async def create_model(
    request: ModelCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    """
    创建模型。

    Args:
        request: 创建请求。
        session: 数据库 session。
        service: 模型服务。

    Returns:
        创建的模型信息。
    """
    logger.info(f"创建模型: {request.name}")

    model = await service.create_model(
        session=session,
        name=request.name,
        provider_id=request.provider_id,
        model_id=request.model_id,
        task_type=request.task_type,
        remark=request.remark,
        tags=request.tags,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        min_p=request.min_p,
        top_a=request.top_a,
        frequency_penalty=request.frequency_penalty,
        presence_penalty=request.presence_penalty,
        repetition_penalty=request.repetition_penalty,
        max_tokens=request.max_tokens,
        context_length=request.context_length,
        deepseek_reasoning_effort=request.deepseek_reasoning_effort,
        deepseek_thinking_type=request.deepseek_thinking_type,
        dimensions=request.dimensions,
    )

    return _to_response(model)


@router.put(
    "/{model_id}",
    response_model=ModelResponse,
    summary="更新模型",
)
async def update_model(
    model_id: str,
    request: ModelUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    """
    更新模型信息。

    Args:
        model_id: 模型 ID。
        request: 更新请求。
        session: 数据库 session。
        service: 模型服务。

    Returns:
        更新后的模型信息。

    Raises:
        HTTPException: 如果模型不存在。
    """
    logger.info(f"更新模型: {model_id}")

    try:
        model = await service.update_model(
            session=session,
            model_id=model_id,
            name=request.name,
            remark=request.remark,
            provider_id=request.provider_id,
            model_identifier=request.model_id,
            task_type=request.task_type,
            tags=request.tags,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            min_p=request.min_p,
            top_a=request.top_a,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            repetition_penalty=request.repetition_penalty,
            max_tokens=request.max_tokens,
            context_length=request.context_length,
            deepseek_reasoning_effort=request.deepseek_reasoning_effort,
            deepseek_thinking_type=request.deepseek_thinking_type,
            dimensions=request.dimensions,
        )

        return _to_response(model)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除模型",
)
async def delete_model(
    model_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> None:
    """
    删除模型。

    Args:
        model_id: 模型 ID。
        session: 数据库 session。
        service: 模型服务。

    Raises:
        HTTPException: 如果模型不存在。
    """
    logger.info(f"删除模型: {model_id}")

    try:
        await service.delete_model(session, model_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
