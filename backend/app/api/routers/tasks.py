# -*- coding: utf-8 -*-
"""Task Router - 任务API路由。"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.modes import AgentMode
from app.agent_runtime.attachments import delete_attachments_for_task
from app.agent_runtime.persistence.child_runs import list_child_runs_for_parent
from app.agent_runtime.persistence.task_projection import load_task_messages_for_agent_session
from app.agent_runtime.runner.checkpointer import delete_checkpoints_for_thread, get_checkpointer

from app.api.schemas.task import (
    TaskListItem,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.models.revision import Revision
from app.storage.services import task_service

router = APIRouter(tags=["Tasks"])


def _require_agent_mode(mode: str) -> AgentMode:
    if mode != "agent":
        raise ValueError(f"Unsupported task mode: {mode}")
    return cast(AgentMode, mode)


async def _list_descendant_child_thread_ids(
    session: AsyncSession,
    parent_session_id: str,
) -> list[str]:
    child_thread_ids: list[str] = []
    for child_run in await list_child_runs_for_parent(session, parent_session_id):
        child_thread_ids.extend(
            await _list_descendant_child_thread_ids(session, child_run.child_thread_id)
        )
        child_thread_ids.append(child_run.child_thread_id)
    return child_thread_ids


async def _list_task_checkpoint_thread_ids(
    session: AsyncSession,
    session_id: str | None,
) -> list[str]:
    if not session_id:
        return []
    return [*await _list_descendant_child_thread_ids(session, session_id), session_id]


async def _has_pending_interrupt(checkpointer, session_id: str | None) -> bool:
    if not session_id:
        return False
    checkpoint = await checkpointer.aget_tuple({"configurable": {"thread_id": session_id}})
    return any(
        len(pending_write) >= 3
        and pending_write[1] == "__interrupt__"
        and isinstance(pending_write[2], list)
        and pending_write[2]
        for pending_write in checkpoint.pending_writes or []
    ) if checkpoint is not None else False


async def _delete_checkpoint_threads(
    session_id: str | None,
    thread_ids: list[str],
) -> None:
    for thread_id in thread_ids:
        deleted_rows = await delete_checkpoints_for_thread(thread_id)
        logger.bind(session_id=session_id, thread_id=thread_id).info(
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
            cost=task.cost,
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
        checkpointer = await get_checkpointer()
        pending_interrupts = {
            task.id: await _has_pending_interrupt(checkpointer, task.agent_session_id)
            for task in result.items
        }
        current_revision_ids = {
            task.current_revision_id
            for task in result.items
            if task.current_revision_id is not None
        }
        cancelled_revision_ids: set[str] = set()
        if current_revision_ids:
            cancelled_revision_result = await session.execute(
                select(col(Revision.id)).where(
                    col(Revision.id).in_(current_revision_ids),
                    col(Revision.status) == "cancelled",
                )
            )
            cancelled_revision_ids = set(cancelled_revision_result.scalars().all())

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
                cost=task.cost,
                is_running=task.is_running
                or (
                    pending_interrupts[task.id]
                    and task.current_revision_id not in cancelled_revision_ids
                ),
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
            cost=task.cost,
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
        checkpoint_thread_ids = await _list_task_checkpoint_thread_ids(
            session,
            task.agent_session_id,
        )
        await delete_attachments_for_task(session, task_id=task.id)
        await task_service.delete_task(session, task_id)
        await session.commit()
        await _delete_checkpoint_threads(task.agent_session_id, checkpoint_thread_ids)
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

        checkpoint_thread_ids_by_session = {
            task.agent_session_id: await _list_task_checkpoint_thread_ids(
                session,
                task.agent_session_id,
            )
            for task in deletable_tasks
            if task.agent_session_id
        }
        for task in deletable_tasks:
            await delete_attachments_for_task(session, task_id=task.id)
            await task_service.delete_task(session, task.id)

        await session.commit()
        for task in deletable_tasks:
            await _delete_checkpoint_threads(
                task.agent_session_id,
                checkpoint_thread_ids_by_session.get(task.agent_session_id, []),
            )
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
