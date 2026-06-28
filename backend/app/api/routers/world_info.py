# -*- coding: utf-8 -*-
"""
WorldInfo Router - 世界书 CRUD API。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.world_info import (
    WorldInfoCreate,
    WorldInfoListResponse,
    WorldInfoResponse,
    WorldInfoUpdate,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import world_info_service
from app.storage.services.world_info_service import ProjectAlreadyBoundError

router = APIRouter(tags=["world-info"])


# ============== 世界书端点 ==============


@router.post(
    "/world-info",
    response_model=WorldInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建世界书",
)
async def create_world_info(
    data: WorldInfoCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse:
    """
    创建世界书。

    Args:
        data: 创建请求数据，包含名称和可选的项目 ID。
        session: 数据库 session。

    Returns:
        创建的世界书。

    Raises:
        HTTPException: 项目不存在或项目已绑定其他世界书。
    """
    try:
        logger.info(f"创建世界书: name={data.name}, project_id={data.project_id}")
        world_info = await world_info_service.create_world_info(
            session,
            name=data.name,
            project_id=data.project_id,
            description=data.description,
        )
        return WorldInfoResponse.model_validate(world_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ProjectAlreadyBoundError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/world-info",
    response_model=WorldInfoListResponse,
    summary="获取世界书列表",
)
async def list_world_info(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 50,
) -> WorldInfoListResponse:
    """
    获取所有世界书列表。

    Args:
        session: 数据库 session。
        page: 页码。
        page_size: 每页数量。

    Returns:
        世界书列表。
    """
    result = await world_info_service.list_world_info(
        session, page=page, page_size=page_size
    )
    return WorldInfoListResponse(
        items=[WorldInfoResponse.model_validate(w) for w in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


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
    response_model=WorldInfoResponse | None,
    summary="获取项目的世界书",
)
async def get_project_world_info(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse | None:
    """
    获取项目关联的世界书。

    Args:
        project_id: 项目 ID。
        session: 数据库 session。

    Returns:
        世界书，如果不存在则返回 null。

    Raises:
        HTTPException: 项目不存在。
    """
    try:
        world_info = await world_info_service.get_world_info_by_project(
            session, project_id
        )
        if world_info is None:
            return None
        return WorldInfoResponse.model_validate(world_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/world-info/{world_info_id}",
    response_model=WorldInfoResponse,
    summary="更新世界书",
)
async def update_world_info(
    world_info_id: str,
    data: WorldInfoUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoResponse:
    """
    更新世界书。

    Args:
        world_info_id: 世界书 ID。
        data: 更新请求数据。
        session: 数据库 session。

    Returns:
        更新后的世界书。

    Raises:
        HTTPException: 世界书不存在或项目绑定冲突。
    """
    try:
        logger.info(f"更新世界书: {world_info_id}")
        world_info = await world_info_service.update_world_info(
            session,
            world_info_id,
            name=data.name,
            project_id=data.project_id,
            unbind_project=data.unbind_project,
            description=data.description,
        )
        return WorldInfoResponse.model_validate(world_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ProjectAlreadyBoundError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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
