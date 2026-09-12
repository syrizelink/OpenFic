# -*- coding: utf-8 -*-
"""
Model Router - API model.
"""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.model import (
    ModelCreateRequest,
    ModelResponse,
    ModelUpdateRequest,
    ModelValidationResponse,
    TaskType,
)
from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.models.services import ModelService

router = APIRouter(prefix="/models", tags=["models"])
_SUPPORTED_TASK_TYPES = frozenset({"llm", "embedding", "rerank"})


def get_model_service() -> ModelService:
    """Mengambil instance layanan model."""
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
        input_price=m.input_price,
        output_price=m.output_price,
        cache_read_price=m.cache_read_price,
        cache_write_price=m.cache_write_price,
        dimensions=m.dimensions,
        is_builtin=m.is_builtin,
        created_at=m.created_at.isoformat(),
        updated_at=m.updated_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[ModelResponse],
    summary="Mengambil semua model",
)
async def get_models(
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
    provider_id: str | None = None,
    task_type: str | None = None,
) -> list[ModelResponse]:
    """
    Mengambil semua model atau memfilter berdasarkan kondisi.

    Args:
        session: Session basis data.
        service: Layanan model.
        provider_id: Filter ID penyedia (opsional).
        task_type: Filter tipe tugas (opsional, llm atau embedding).

    Returns:
        Daftar model.
    """
    if provider_id:
        models = await service.get_models_by_provider(session, provider_id, task_type)
    else:
        all_models = await service.get_all_models(session)
        # Memfilter bila task_type ditentukan
        if task_type:
            models = [m for m in all_models if m.task_type == task_type]
        else:
            models = all_models

    return [_to_response(m) for m in models]


@router.post(
    "/{model_id}/validate",
    response_model=ModelValidationResponse,
    summary="Memvalidasi koneksi model",
)
async def validate_model_connection(
    model_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelValidationResponse:
    """Mengirim permintaan non-streaming minimal dengan model tertentu untuk memvalidasi koneksinya."""
    try:
        await service.validate_model_connection(session, model_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except Exception:
        logger.opt(exception=True).warning("Gagal memvalidasi koneksi model: model_id={}", model_id)
        return ModelValidationResponse(success=False, message="Validasi koneksi model gagal")

    return ModelValidationResponse(success=True, message="Validasi koneksi model berhasil")


@router.get(
    "/{model_id}",
    response_model=ModelResponse,
    summary="Mengambil model",
)
async def get_model(
    model_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    """
    Mengambil model berdasarkan ID.

    Args:
        model_id: ID model.
        session: Session basis data.
        service: Layanan model.

    Returns:
        Informasi model.

    Raises:
        HTTPException: Bila model tidak ditemukan.
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
    summary="Membuat model",
)
async def create_model(
    request: ModelCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    """
    Membuat model.

    Args:
        request: Permintaan pembuatan.
        session: Session basis data.
        service: Layanan model.

    Returns:
        Informasi model yang dibuat.
    """
    await require_agent_settings_unlocked(session)
    logger.info(f"Membuat model: {request.name}")

    try:
        model = await service.create_model(
            session=session,
            name=request.name,
            provider_id=request.provider_id,
            model_id=request.model_id,
            task_type=request.task_type,
            remark=request.remark,
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
            input_price=request.input_price,
            output_price=request.output_price,
            cache_read_price=request.cache_read_price,
            cache_write_price=request.cache_write_price,
            dimensions=request.dimensions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _to_response(model)


@router.put(
    "/{model_id}",
    response_model=ModelResponse,
    summary="Memperbarui model",
)
async def update_model(
    model_id: str,
    request: ModelUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    """
    Memperbarui informasi model.

    Args:
        model_id: ID model.
        request: Permintaan pembaruan.
        session: Session basis data.
        service: Layanan model.

    Returns:
        Informasi model setelah diperbarui.

    Raises:
        HTTPException: Bila model tidak ditemukan.
    """
    await require_agent_settings_unlocked(session)
    logger.info(f"Memperbarui model: {model_id}")

    try:
        model = await service.update_model(
            session=session,
            model_id=model_id,
            name=request.name,
            remark=request.remark,
            provider_id=request.provider_id,
            model_identifier=request.model_id,
            task_type=request.task_type,
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
            input_price=request.input_price,
            output_price=request.output_price,
            cache_read_price=request.cache_read_price,
            cache_write_price=request.cache_write_price,
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
    summary="Menghapus model",
)
async def delete_model(
    model_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> None:
    """
    Menghapus model.

    Args:
        model_id: ID model.
        session: Session basis data.
        service: Layanan model.

    Raises:
        HTTPException: Bila model tidak ditemukan.
    """
    await require_agent_settings_unlocked(session)
    logger.info(f"Menghapus model: {model_id}")

    try:
        await service.delete_model(session, model_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
