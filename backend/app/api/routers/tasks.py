# -*- coding: utf-8 -*-
"""Task Router - 任务API路由。"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.modes import AgentMode
from app.agent_runtime.persistence.task_projection import load_task_messages_for_agent_session
from app.agent_runtime.runner.checkpointer import delete_checkpoints_for_thread

from app.api.schemas.task import (
    TaskListItem,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import task_service

router = APIRouter(tags=["Tasks"])


def _require_agent_mode(mode: str) -> AgentMode:
    if mode != "agent":
        raise ValueError(f"Unsupported task mode: {mode}")
    return cast(AgentMode, mode)


async def _cleanup_task_checkpoints(session_id: str | None) -> None:
    if not session_id:
        return
    deleted_rows = await delete_checkpoints_for_thread(session_id)
    logger.bind(session_id=session_id).info(
        "Deleted {} checkpoint rows for task cleanup",
        deleted_rows,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    try:
        task = await task_service.get_task(session, task_id)
        if task.agent_session_id:
            task_messages = await load_task_messages_for_agent_session(
                session,
                task.agent_session_id,
            )
        else:
            task_messages = []

        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            mode=_require_agent_mode(task.mode),
            messages=task_messages,
            token_input=task.token_input,
            token_output=task.token_output,
            token_cache=task.token_cache,
            context_input_tokens=task.context_input_tokens,
            current_revision_id=task.current_revision_id,
            current_message_id=task.current_message_id,
            agent_session_id=task.agent_session_id,
            is_running=task.is_running,
            is_favorited=task.is_favorited,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/projects/{project_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: str,
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    favorited: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> TaskListResponse:
    if "mode" in request.query_params:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="mode 查询参数已移除",
        )

    try:
        result = await task_service.list_tasks(
            session,
            project_id=project_id,
            limit=limit,
            offset=offset,
            search_query=search,
            favorited_only=favorited,
        )

        items = [
            TaskListItem(
                id=task.id,
                project_id=task.project_id,
                title=task.title,
                mode=_require_agent_mode(task.mode),
                token_input=task.token_input,
                token_output=task.token_output,
                token_cache=task.token_cache,
                context_input_tokens=task.context_input_tokens,
                is_running=task.is_running,
                is_favorited=task.is_favorited,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task in result.items
        ]

        return TaskListResponse(items=items, total=result.total)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    try:
        task = await task_service.update_task(
            session,
            task_id=task_id,
            title=request.title,
            is_favorited=request.is_favorited,
        )
        await session.commit()
        if task.agent_session_id:
            task_messages = await load_task_messages_for_agent_session(
                session,
                task.agent_session_id,
            )
        else:
            task_messages = []

        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            mode=_require_agent_mode(task.mode),
            messages=task_messages,
            token_input=task.token_input,
            token_output=task.token_output,
            token_cache=task.token_cache,
            context_input_tokens=task.context_input_tokens,
            current_revision_id=task.current_revision_id,
            current_message_id=task.current_message_id,
            agent_session_id=task.agent_session_id,
            is_running=task.is_running,
            is_favorited=task.is_favorited,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"更新任务失败：{e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新任务失败：{str(e)}",
        )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        task = await task_service.get_task(session, task_id)
        if task.is_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="任务运行中，不能删除",
            )
        await task_service.delete_task(session, task_id)
        await session.commit()
        await _cleanup_task_checkpoints(task.agent_session_id)
    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"删除任务失败：{e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败：{str(e)}",
        )


@router.delete("/projects/{project_id}/tasks", status_code=status.HTTP_200_OK)
async def delete_all_tasks(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    try:
        tasks = (await task_service.list_tasks(session, project_id)).items
        deletable_tasks = [task for task in tasks if not task.is_running]
        skipped_running_count = len(tasks) - len(deletable_tasks)

        for task in deletable_tasks:
            await task_service.delete_task(session, task.id)

        await session.commit()
        for task in deletable_tasks:
            await _cleanup_task_checkpoints(task.agent_session_id)
        deleted_count = len(deletable_tasks)
        logger.info(
            f"已删除项目 {project_id} 下的 {deleted_count} 个任务，跳过 {skipped_running_count} 个运行中任务"
        )
        return {
            "deleted_count": deleted_count,
            "skipped_running_count": skipped_running_count,
        }
    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"批量删除任务失败：{e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除任务失败：{str(e)}",
        )
