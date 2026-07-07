# -*- coding: utf-8 -*-
"""WorldInfo Service - 世界书业务逻辑层。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.world_info import WorldInfo
from app.storage.repos import project_repo, world_info_entry_repo, world_info_repo

INTERNAL_WORLD_INFO_NAME = ""


# ============== 世界书操作 ==============


async def get_world_info(session: AsyncSession, world_info_id: str) -> WorldInfo:
    """
    获取世界书。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Returns:
        世界书实例。

    Raises:
        NotFoundError: 世界书不存在。
    """
    world_info = await world_info_repo.get_by_id(session, world_info_id)
    if world_info is None:
        raise NotFoundError(f"世界书不存在: {world_info_id}")
    return world_info


async def get_or_create_world_info_by_project(
    session: AsyncSession, project_id: str
) -> WorldInfo:
    """根据项目 ID 获取项目唯一世界书，不存在时自动创建。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    world_info = await world_info_repo.get_by_project_id(session, project_id)
    if world_info is not None:
        return world_info

    return await world_info_repo.create(
        session,
        WorldInfo(
            project_id=project_id,
            name=INTERNAL_WORLD_INFO_NAME,
            description="",
        ),
    )


async def delete_world_info(session: AsyncSession, world_info_id: str) -> None:
    """
    删除世界书及其所有条目。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Raises:
        NotFoundError: 世界书不存在。
    """
    world_info = await get_world_info(session, world_info_id)

    # 先删除所有条目
    await world_info_entry_repo.delete_by_world_info(session, world_info_id)

    # 再删除世界书
    await world_info_repo.delete(session, world_info)
