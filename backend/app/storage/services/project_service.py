# -*- coding: utf-8 -*-
"""
Project Service - 项目业务逻辑层。
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.storage import delete_cover_file, save_cover_file
from app.storage.models.project import Project
from app.storage.repos import chapter_repo, project_repo, volume_repo
from app.storage.services import volume_service


@dataclass
class ProjectListResult:
    """项目列表结果。"""

    items: list[Project]
    total: int
    page: int
    page_size: int


async def create_project(
    session: AsyncSession,
    title: str,
    description: str | None = None,
    cover_file: UploadFile | None = None,
) -> Project:
    """
    创建项目。

    Args:
        session: 数据库 session。
        title: 项目标题。
        description: 项目简介，可选。
        cover_file: 封面文件，可选。

    Returns:
        创建的项目实例。
    """
    project = Project(title=title, description=description)
    project = await project_repo.create(session, project)
    await volume_service.create_default_volume(session, project.id)

    # 如果提供了封面文件，保存封面
    if cover_file:
        cover_path = await save_cover_file(project.id, cover_file)
        project.cover_path = cover_path
        project = await project_repo.update(session, project)

    return project


async def get_project(session: AsyncSession, project_id: str) -> Project:
    """
    获取项目。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        项目实例。

    Raises:
        NotFoundError: 项目不存在。
    """
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    return project


async def list_projects(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> ProjectListResult:
    """
    获取项目列表。

    Args:
        session: 数据库 session。
        page: 页码，从 1 开始。
        page_size: 每页数量。

    Returns:
        项目列表结果。
    """
    offset = (page - 1) * page_size
    items = await project_repo.list_all(session, offset=offset, limit=page_size)
    total = await project_repo.count(session)
    return ProjectListResult(items=items, total=total, page=page, page_size=page_size)


async def update_project(
    session: AsyncSession,
    project_id: str,
    title: str | None = None,
    description: str | None = None,
    cover_file: UploadFile | None = None,
) -> Project:
    """
    更新项目。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        title: 新标题，可选。
        description: 新简介，可选。
        cover_file: 新封面文件，可选。

    Returns:
        更新后的项目实例。

    Raises:
        NotFoundError: 项目不存在。
    """
    project = await get_project(session, project_id)

    if title is not None:
        project.title = title
    if description is not None:
        project.description = description

    # 如果提供了新封面，替换原有封面
    if cover_file:
        # 删除旧封面（如果存在）
        if project.cover_path:
            delete_cover_file(project.id)
        # 保存新封面
        cover_path = await save_cover_file(project.id, cover_file)
        project.cover_path = cover_path

    project.updated_at = datetime.now(UTC)
    return await project_repo.update(session, project)


async def delete_project(session: AsyncSession, project_id: str) -> None:
    """
    删除项目。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Raises:
        NotFoundError: 项目不存在。
    """
    project = await get_project(session, project_id)

    # 删除项目下的所有章节
    await chapter_repo.delete_by_project(session, project_id)
    await volume_repo.delete_by_project(session, project_id)

    # 删除封面文件（如果存在）
    if project.cover_path:
        delete_cover_file(project.id)

    await project_repo.delete(session, project)
