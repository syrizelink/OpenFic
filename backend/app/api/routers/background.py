"""Background job API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.background import (
    BackgroundCancelJobRequest,
    BackgroundJobEventListResponse,
    BackgroundJobEventResponse,
    BackgroundJobItemListResponse,
    BackgroundJobItemResponse,
    BackgroundJobListResponse,
    BackgroundJobResponse,
)
from app.background.jobs import service as background_service
from app.background.runtime.supervisor import get_background_supervisor
from app.storage.database import get_session

router = APIRouter(prefix="/background", tags=["Background"])


@router.get("/jobs/{job_id}", response_model=BackgroundJobResponse)
async def get_background_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> BackgroundJobResponse:
    job = await background_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="后台任务不存在")
    return _to_job_response(job)


@router.get("/jobs", response_model=BackgroundJobListResponse)
async def list_background_jobs(
    subject_type: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> BackgroundJobListResponse:
    jobs = await background_service.list_jobs(
        session,
        subject_type=subject_type,
        subject_id=subject_id,
        status=status_filter,
        job_type=type_filter,
        limit=limit,
        offset=offset,
    )
    return BackgroundJobListResponse(items=[_to_job_response(job) for job in jobs])


@router.get("/jobs/{job_id}/events", response_model=BackgroundJobEventListResponse)
async def list_background_job_events(
    job_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> BackgroundJobEventListResponse:
    job = await background_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="后台任务不存在")
    events = await background_service.list_job_events(
        session,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )
    return BackgroundJobEventListResponse(items=[_to_event_response(event) for event in events])


@router.get("/jobs/{job_id}/items", response_model=BackgroundJobItemListResponse)
async def list_background_job_items(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> BackgroundJobItemListResponse:
    job = await background_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="后台任务不存在")
    items = await background_service.list_job_items(session, job_id=job_id)
    return BackgroundJobItemListResponse(items=[_to_item_response(item) for item in items])


@router.post("/jobs/{job_id}/cancel", response_model=BackgroundJobResponse)
async def cancel_background_job(
    job_id: str,
    data: BackgroundCancelJobRequest,
    session: AsyncSession = Depends(get_session),
) -> BackgroundJobResponse:
    job = await background_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="后台任务不存在")
    job = await background_service.cancel_job(
        session,
        get_background_supervisor().create_event_publisher(),
        job,
        reason=data.reason,
    )
    await background_service.commit_and_notify(session)
    if job.type == "summary_batch":
        get_background_supervisor().cancel_running_summary_batch(job.id)
    return _to_job_response(job)


def _to_job_response(job) -> BackgroundJobResponse:
    return BackgroundJobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        queue=job.queue,
        subject_type=job.subject_type,
        subject_id=job.subject_id,
        payload=background_service.parse_json_object(job.payload_json),
        context=background_service.parse_json_object(job.context_json),
        progress=background_service.parse_json_object(job.progress_json),
        result=background_service.parse_json_object(job.result_json),
        error=background_service.parse_json_object(job.error_json),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        timeout_seconds=job.timeout_seconds,
        next_run_at=job.next_run_at,
        locked_by=job.locked_by,
        locked_at=job.locked_at,
        heartbeat_at=job.heartbeat_at,
        lease_expires_at=job.lease_expires_at,
        cancel_requested_at=job.cancel_requested_at,
        cancel_reason=job.cancel_reason,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _to_event_response(event) -> BackgroundJobEventResponse:
    return BackgroundJobEventResponse(
        id=event.id,
        job_id=event.job_id,
        item_id=event.item_id,
        sequence=event.sequence,
        event_type=event.event_type,
        payload=background_service.parse_json_object(event.payload_json),
        created_at=event.created_at,
    )


def _to_item_response(item) -> BackgroundJobItemResponse:
    return BackgroundJobItemResponse(
        id=item.id,
        job_id=item.job_id,
        item_key=item.item_key,
        type=item.type,
        status=item.status,
        payload=background_service.parse_json_object(item.payload_json),
        result=background_service.parse_json_object(item.result_json),
        error=background_service.parse_json_object(item.error_json),
        progress=background_service.parse_json_object(item.progress_json),
        order_index=item.order_index,
        created_at=item.created_at,
        updated_at=item.updated_at,
        started_at=item.started_at,
        finished_at=item.finished_at,
    )
