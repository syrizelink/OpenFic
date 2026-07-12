# -*- coding: utf-8 -*-
"""Project chapter retrieval index APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.retrieval_index import (
    IndexOverallStatusResponse,
    IndexProjectStatusResponse,
    IndexStartResponse,
    IndexStopResponse,
)
from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.background.jobs import service as background_service
from app.background.jobs.constants import JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH
from app.background.jobs.states import JOB_STATUS_PENDING, JOB_STATUS_RUNNING
from app.background.runtime.supervisor import get_background_supervisor
from app.retrieval.chapter_index import (
    INDEX_MODE_ALL,
    INDEX_MODE_OFF,
    compute_project_index_status,
    enqueue_project_index_update,
    get_index_settings,
    is_project_index_enabled,
    resolve_index_embedding_model,
)
from app.retrieval.index_status import schedule_emit_index_status
from app.storage.database import get_session
from app.storage.repos import project_repo

router = APIRouter(prefix="/projects/{project_id}/retrieval/index", tags=["retrieval"])
global_router = APIRouter(prefix="/retrieval/index", tags=["retrieval"])


_BLOCKING_DETAIL = "未配置可用的嵌入模型，无法操作检索索引"


async def _require_project(session: AsyncSession, project_id: str):
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在: {project_id}",
        )
    return project


def _status_to_response(status_obj) -> IndexProjectStatusResponse:
    payload = status_obj.to_payload()
    return IndexProjectStatusResponse(**payload)


@router.get("/status", response_model=IndexProjectStatusResponse)
async def get_project_retrieval_index_status(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexProjectStatusResponse:
    project = await _require_project(session, project_id)
    status_obj = await compute_project_index_status(
        session, project_id=project_id, title=project.title
    )
    return _status_to_response(status_obj)


@router.post("/start", response_model=IndexStartResponse)
async def start_project_retrieval_index(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexStartResponse:
    await require_agent_settings_unlocked(session)
    await _require_project(session, project_id)
    config = await get_index_settings(session)
    if not is_project_index_enabled(config, project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前项目未启用索引",
        )
    if await resolve_index_embedding_model(session, config) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_BLOCKING_DETAIL,
        )

    result = await enqueue_project_index_update(session, project_id=project_id)
    schedule_emit_index_status(session, project_id)
    await background_service.commit_and_notify(session)
    return IndexStartResponse(
        project_id=project_id,
        enqueued_count=result.enqueued_count if result else 0,
        skipped_count=result.skipped_count if result else 0,
    )


@router.post("/stop", response_model=IndexStopResponse)
async def stop_project_retrieval_index(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexStopResponse:
    await require_agent_settings_unlocked(session)
    await _require_project(session, project_id)
    publisher = get_background_supervisor().create_event_publisher()
    jobs = await background_service.list_jobs(
        session,
        subject_type="project",
        subject_id=project_id,
        statuses={JOB_STATUS_PENDING, JOB_STATUS_RUNNING},
        job_type=JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH,
    )
    for job in jobs:
        await background_service.cancel_job(
            session,
            publisher,
            job,
            reason="用户停止索引",
        )
    schedule_emit_index_status(session, project_id)
    await background_service.commit_and_notify(session)
    for job in jobs:
        get_background_supervisor().cancel_running_index_batch(job.id)
    return IndexStopResponse(project_id=project_id, stopped_count=len(jobs))


@global_router.get("/status", response_model=IndexOverallStatusResponse)
async def get_overall_retrieval_index_status(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexOverallStatusResponse:
    config = await get_index_settings(session)
    embedding_configured = await resolve_index_embedding_model(session, config) is not None

    projects: list[IndexProjectStatusResponse] = []
    total_chapters = 0
    indexed_count = 0
    pending_count = 0
    in_progress_count = 0
    failed_count = 0

    if config.mode != INDEX_MODE_OFF:
        all_projects = await project_repo.list_all(session, offset=0, limit=10000)
        enabled_ids = (
            {p.id for p in all_projects}
            if config.mode == INDEX_MODE_ALL
            else set(config.enabled_projects)
        )
        for project in all_projects:
            if project.id not in enabled_ids:
                continue
            status_obj = await compute_project_index_status(
                session, project_id=project.id, title=project.title
            )
            projects.append(_status_to_response(status_obj))
            total_chapters += status_obj.total_chapters
            indexed_count += status_obj.indexed_count
            pending_count += status_obj.pending_count
            in_progress_count += status_obj.in_progress_count
            failed_count += status_obj.failed_count

    return IndexOverallStatusResponse(
        mode=config.mode,
        embedding_model_configured=embedding_configured,
        total_projects=len(projects),
        total_chapters=total_chapters,
        indexed_count=indexed_count,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        failed_count=failed_count,
        projects=projects,
    )
