# -*- coding: utf-8 -*-
"""WorldInfo Router - API buku dunia."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.world_info import WorldInfoResponse
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import world_info_service

router = APIRouter(tags=["world-info"])


# ============== Endpoint buku dunia ==============


@router.get(
    "/world-info/{world_info_id}",
    response_model=WorldInfoResponse,
    summary="Mengambil buku dunia",
)
async def get_world_info(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse:
    """
    Mengambil buku dunia berdasarkan ID.

    Args:
        world_info_id: ID buku dunia.
        session: Session basis data.

    Returns:
        Buku dunia.

    Raises:
        HTTPException: Buku dunia tidak ditemukan.
    """
    try:
        world_info = await world_info_service.get_world_info(session, world_info_id)
        return WorldInfoResponse.model_validate(world_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/world-info",
    response_model=WorldInfoResponse,
    summary="Mengambil buku dunia milik proyek",
)
async def get_project_world_info(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse:
    """
    Mengambil buku dunia yang terkait dengan proyek.

    Args:
        project_id: ID proyek.
        session: Session basis data.

        Returns:
            Buku dunia, dibuat otomatis bila belum ada.

    Raises:
        HTTPException: Proyek tidak ditemukan.
    """
    try:
        world_info = await world_info_service.get_or_create_world_info_by_project(
            session, project_id
        )
        return WorldInfoResponse.model_validate(world_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/world-info/{world_info_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Menghapus buku dunia",
)
async def delete_world_info(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    Menghapus buku dunia beserta seluruh entrinya.

    Args:
        world_info_id: ID buku dunia.
        session: Session basis data.

    Raises:
        HTTPException: Buku dunia tidak ditemukan.
    """
    try:
        logger.info(f"Menghapus buku dunia: {world_info_id}")
        await world_info_service.delete_world_info(session, world_info_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
