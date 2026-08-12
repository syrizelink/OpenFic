# -*- coding: utf-8 -*-
"""
Projects Router - 项目 CRUD API。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.attachments import delete_attachments_for_task
from app.agent_runtime.persistence.model import AgentChildRun
from app.agent_runtime.runner.checkpointer import delete_checkpoints_for_thread
from app.api.schemas.project import (
    ProjectListResponse,
    ProjectResponse,
)
from app.core.errors import NotFoundError
from app.core.storage import get_cover_url
from app.storage.database import get_session
from app.storage.models.task import Task
from app.storage.services import project_service, task_service

router = APIRouter(prefix="/projects", tags=["projects"])


async def _list_project_checkpoint_thread_ids(
    session: AsyncSession,
    project_id: str,
) -> list[str]:
    task_result = await session.execute(
        select(col(Task.agent_session_id)).where(col(Task.project_id) == project_id)
    )
    child_result = await session.execute(
        select(col(AgentChildRun.child_thread_id)).where(
            col(AgentChildRun.parent_task_id).in_(
                select(col(Task.id)).where(col(Task.project_id) == project_id)
            )
        )
    )
    return [
        *(
            session_id
            for session_id in task_result.scalars().all()
            if session_id
        ),
        *(
            thread_id
            for thread_id in child_result.scalars().all()
            if thread_id
        ),
    ]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建项目",
)
async def create_project(
    title: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """
    创建新的小说项目。

    Args:
        title: 项目标题。
        description: 项目简介（可选）。
        cover: 封面图片（可选）。
        session: 数据库 session。

    Returns:
        创建的项目。
    """
    logger.info(f"创建项目: {title}")
    project = await project_service.create_project(
        session,
        title=title,
        description=description,
        cover_file=cover,
    )
    return _project_to_response(project)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="获取项目列表",
)
async def list_projects(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    search: Annotated[str | None, Query(description="按项目标题或简介搜索")] = None,
    sort_by: Annotated[
        Literal["updated_at", "created_at", "title"],
        Query(description="排序字段"),
    ] = "updated_at",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(description="排序方向")
    ] = "desc",
) -> ProjectListResponse:
    """
    获取项目列表，支持分页。

    Args:
        session: 数据库 session。
        page: 页码，从 1 开始。
        page_size: 每页数量，最大 100。
        search: 项目标题或简介搜索词。
        sort_by: 排序字段，可选 updated_at、created_at、title。
        sort_order: 排序方向，可选 asc、desc。

    Returns:
        项目列表。
    """
    result = await project_service.list_projects(
        session,
        page=page,
        page_size=page_size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ProjectListResponse(
        items=[_project_to_response(p) for p in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="获取项目详情",
)
async def get_project(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    """
    获取单个项目的详细信息。

    Args:
        project_id: 项目 ID。
        session: 数据库 session。

    Returns:
        项目详情。

    Raises:
        HTTPException: 项目不存在时返回 404。
    """
    try:
        project = await project_service.get_project(session, project_id)
        return _project_to_response(project)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="更新项目",
)
async def update_project(
    project_id: str,
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """
    更新项目信息。

    Args:
        project_id: 项目 ID。
        title: 新标题（可选）。
        description: 新简介（可选）。
        cover: 新封面图片（可选）。
        session: 数据库 session。

    Returns:
        更新后的项目。

    Raises:
        HTTPException: 项目不存在时返回 404。
    """
    try:
        logger.info(f"更新项目: {project_id}")
        project = await project_service.update_project(
            session,
            project_id,
            title=title,
            description=description,
            cover_file=cover,
        )
        return _project_to_response(project)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除项目",
)
async def delete_project(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    删除项目。

    Args:
        project_id: 项目 ID。
        session: 数据库 session。

    Raises:
        HTTPException: 项目不存在时返回 404。
    """
    try:
        logger.info(f"删除项目: {project_id}")
        tasks = (await task_service.list_tasks(session, project_id)).items
        if any(task.is_running for task in tasks):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="项目存在运行中任务，不能删除",
            )
        checkpoint_thread_ids = await _list_project_checkpoint_thread_ids(session, project_id)
        for task in tasks:
            await delete_attachments_for_task(session, task_id=task.id)
        await project_service.delete_project(session, project_id)
        await session.commit()
        for thread_id in checkpoint_thread_ids:
            deleted_rows = await delete_checkpoints_for_thread(thread_id)
            logger.bind(project_id=project_id, thread_id=thread_id).info(
                "Deleted {} checkpoint rows for project cleanup",
                deleted_rows,
            )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def _project_to_response(project) -> ProjectResponse:
    """
    将 Project 模型转换为 ProjectResponse，添加 cover_url。

    Args:
        project: Project 模型实例。

    Returns:
        ProjectResponse。
    """
    return ProjectResponse(
        id=project.id,
        title=project.title,
        description=project.description,
        word_count=project.word_count,
        chapter_count=project.chapter_count,
        cover_url=get_cover_url(project.cover_path),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
