# -*- coding: utf-8 -*-
"""
WorldInfo Service - 世界书业务逻辑层。
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.world_info import WorldInfo
from app.storage.repos import project_repo, world_info_entry_repo, world_info_repo


class WorldInfoExistsError(Exception):
    """世界书已存在错误。"""

    pass


class ProjectAlreadyBoundError(Exception):
    """项目已绑定世界书错误。"""

    pass


@dataclass
class WorldInfoListResult:
    """世界书列表结果。"""

    items: list[WorldInfo]
    total: int
    page: int
    page_size: int


# ============== 世界书操作 ==============


async def create_world_info(
    session: AsyncSession,
    name: str,
    project_id: str | None = None,
    description: str = "",
) -> WorldInfo:
    """
    创建世界书。

    Args:
        session: 数据库 session。
        name: 世界书名称。
        project_id: 关联的项目 ID，可选。
        description: 世界书描述。

    Returns:
        创建的世界书实例。

    Raises:
        NotFoundError: 项目不存在。
        ProjectAlreadyBoundError: 项目已绑定其他世界书。
    """
    # 如果指定了项目，检查项目是否存在以及是否已有世界书
    if project_id is not None:
        project = await project_repo.get_by_id(session, project_id)
        if project is None:
            raise NotFoundError(f"项目不存在: {project_id}")

        existing = await world_info_repo.get_by_project_id(session, project_id)
        if existing is not None:
            raise ProjectAlreadyBoundError(f"项目已绑定世界书: {project_id}")

    world_info = WorldInfo(project_id=project_id, name=name, description=description)
    return await world_info_repo.create(session, world_info)


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


async def get_world_info_by_project(
    session: AsyncSession, project_id: str
) -> WorldInfo | None:
    """
    根据项目 ID 获取世界书。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        世界书实例，如果不存在则返回 None。

    Raises:
        NotFoundError: 项目不存在。
    """
    # 检查项目是否存在
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    return await world_info_repo.get_by_project_id(session, project_id)


async def list_world_info(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> WorldInfoListResult:
    """
    获取世界书列表。

    Args:
        session: 数据库 session。
        page: 页码（从 1 开始）。
        page_size: 每页数量。

    Returns:
        世界书列表结果。
    """
    items, total = await world_info_repo.get_all(session, page, page_size)
    return WorldInfoListResult(items=items, total=total, page=page, page_size=page_size)


async def update_world_info(
    session: AsyncSession,
    world_info_id: str,
    name: str | None = None,
    project_id: str | None = None,
    unbind_project: bool = False,
    description: str | None = None,
) -> WorldInfo:
    """
    更新世界书。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。
        name: 新名称。
        project_id: 新的关联项目 ID。
        unbind_project: 是否解除项目绑定。
        description: 新描述。

    Returns:
        更新后的世界书实例。

    Raises:
        NotFoundError: 世界书或项目不存在。
        ProjectAlreadyBoundError: 目标项目已绑定其他世界书。
    """
    world_info = await get_world_info(session, world_info_id)

    if name is not None:
        world_info.name = name

    if description is not None:
        world_info.description = description

    # 解除绑定
    if unbind_project:
        world_info.project_id = None
    # 绑定新项目
    elif project_id is not None:
        # 检查项目是否存在
        project = await project_repo.get_by_id(session, project_id)
        if project is None:
            raise NotFoundError(f"项目不存在: {project_id}")

        # 检查项目是否已绑定其他世界书
        existing = await world_info_repo.get_by_project_id(session, project_id)
        if existing is not None and existing.id != world_info_id:
            raise ProjectAlreadyBoundError(f"项目已绑定其他世界书: {project_id}")

        world_info.project_id = project_id

    world_info.updated_at = datetime.now(UTC)
    return await world_info_repo.update(session, world_info)


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
