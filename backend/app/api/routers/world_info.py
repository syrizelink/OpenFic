# -*- coding: utf-8 -*-
"""WorldInfo Router - 世界书 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.world_info import WorldInfoResponse
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import world_info_service

router = APIRouter(tags=["world-info"])


# ============== 世界书端点 ==============


@router.get(
    "/world-info/{world_info_id}",
    response_model=WorldInfoResponse,
    summary="获取世界书",
)
async def get_world_info(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse:
    """
    根据 ID 获取世界书。

    Args:
        world_info_id: 世界书 ID。
        session: 数据库 session。

    Returns:
        世界书。

    Raises:
        HTTPException: 世界书不存在。
    """
    try:
        world_info = await world_info_service.get_world_info(session, world_info_id)
        return WorldInfoResponse.model_validate(world_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/world-info",
    response_model=WorldInfoResponse,
    summary="获取项目的世界书",
)
async def get_project_world_info(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse:
    """
    获取项目关联的世界书。

    Args:
        project_id: 项目 ID。
        session: 数据库 session。

        Returns:
            世界书，不存在时自动创建。

    Raises:
        HTTPException: 项目不存在。
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
    summary="删除世界书",
)
async def delete_world_info(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    删除世界书及其所有条目。

    Args:
        world_info_id: 世界书 ID。
        session: 数据库 session。

    Raises:
        HTTPException: 世界书不存在。
    """
    try:
        logger.info(f"删除世界书: {world_info_id}")
        await world_info_service.delete_world_info(session, world_info_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
