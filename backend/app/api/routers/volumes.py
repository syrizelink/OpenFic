# -*- coding: utf-8 -*-
"""
Volumes Router - 卷 CRUD API。
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
    summary="创建卷",
)
async def create_volume(
    project_id: str,
    data: VolumeCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """在项目末尾追加卷。"""
    try:
        logger.info(f"创建卷: project_id={project_id}, title={data.title}")
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
    summary="获取卷列表",
)
async def list_volumes(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VolumeResponse]:
    """按 order 获取项目下全部卷。"""
    try:
        volumes = await volume_service.list_volumes(session, project_id)
        return [VolumeResponse.model_validate(volume) for volume in volumes]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/volumes/{volume_id}",
    response_model=VolumeResponse,
    summary="获取卷详情",
)
async def get_volume(
    volume_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """获取单个卷详情。"""
    try:
        volume = await volume_service.get_volume(session, volume_id)
        return VolumeResponse.model_validate(volume)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/volumes/{volume_id}",
    response_model=VolumeResponse,
    summary="更新卷",
)
async def update_volume(
    volume_id: str,
    data: VolumeUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """更新卷名或说明。"""
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
    summary="删除卷",
)
async def delete_volume(
    volume_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    cascade: bool = Query(default=False),
) -> Response:
    """删除卷，非空卷默认返回 409。"""
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
    summary="移动卷",
)
async def move_volume(
    volume_id: str,
    data: VolumeMove,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeResponse:
    """调整卷在项目内的位置。"""
    try:
        volume = await volume_service.move_volume(session, volume_id, data.new_order)
        return VolumeResponse.model_validate(volume)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
