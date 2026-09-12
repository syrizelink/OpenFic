# -*- coding: utf-8 -*-
"""
Volumes Router - API CRUD volume.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.volume import (
    VolumeCreate,
    VolumeMove,
    VolumeResponse,
    VolumeUpdate,
)
from app.core.errors import NotFoundError, ValidationError
from app.storage.database import get_session
from app.storage.services import volume_service

router = APIRouter(tags=["volumes"])


@router.post(
    "/projects/{project_id}/volumes",
    response_model=VolumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat volume",
)
async def create_volume(
    project_id: str,
    data: VolumeCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """Menambahkan volume di akhir proyek."""
    try:
        logger.info(f"Membuat volume: project_id={project_id}, title={data.title}")
        volume = await volume_service.create_volume(
            session,
            project_id=project_id,
            title=data.title,
            description=data.description,
        )
        return VolumeResponse.model_validate(volume)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/volumes",
    response_model=list[VolumeResponse],
    summary="Mengambil daftar volume",
)
async def list_volumes(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VolumeResponse]:
    """Mengambil semua volume pada proyek berdasarkan order."""
    try:
        volumes = await volume_service.list_volumes(session, project_id)
        return [VolumeResponse.model_validate(volume) for volume in volumes]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/volumes/{volume_id}",
    response_model=VolumeResponse,
    summary="Mengambil detail volume",
)
async def get_volume(
    volume_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """Mengambil detail satu volume."""
    try:
        volume = await volume_service.get_volume(session, volume_id)
        return VolumeResponse.model_validate(volume)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/volumes/{volume_id}",
    response_model=VolumeResponse,
    summary="Memperbarui volume",
)
async def update_volume(
    volume_id: str,
    data: VolumeUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """Memperbarui nama atau deskripsi volume."""
    try:
        description = (
            data.description
            if "description" in data.model_fields_set
            else volume_service.UNSET
        )
        volume = await volume_service.update_volume(
            session,
            volume_id,
            title=data.title,
            description=description,
        )
        return VolumeResponse.model_validate(volume)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/volumes/{volume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Menghapus volume",
)
async def delete_volume(
    volume_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    cascade: bool = Query(default=False),
) -> Response:
    """Menghapus volume; volume yang tidak kosong secara default mengembalikan 409."""
    try:
        await volume_service.delete_volume(session, volume_id, cascade=cascade)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/volumes/{volume_id}/move",
    response_model=VolumeResponse,
    summary="Memindahkan volume",
)
async def move_volume(
    volume_id: str,
    data: VolumeMove,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """Menyesuaikan posisi volume di dalam proyek."""
    try:
        volume = await volume_service.move_volume(session, volume_id, data.new_order)
        return VolumeResponse.model_validate(volume)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
