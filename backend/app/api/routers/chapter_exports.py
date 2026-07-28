"""章节导出 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.chapter_export import ChapterExportCreate, ChapterExportResponse
from app.background.jobs import service as background_service
from app.background.runtime.supervisor import get_background_supervisor
from app.chapter_export import service as chapter_export_service
from app.storage.database import get_session


router = APIRouter(tags=["chapter-exports"])


@router.post(
    "/projects/{project_id}/chapter-exports",
    response_model=ChapterExportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建章节导出任务",
)
async def create_chapter_export(
    project_id: str,
    data: ChapterExportCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterExportResponse:
    try:
        plan = await chapter_export_service.create_export_plan(
            session,
            project_id=project_id,
            selected_volume_ids=data.selected_volume_ids,
            included_chapter_ids=data.included_chapter_ids,
            excluded_chapter_ids=data.excluded_chapter_ids,
            local_date=data.local_date.isoformat(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except chapter_export_service.ChapterExportSelectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job = await background_service.submit_job(
        session,
        job_type=chapter_export_service.EXPORT_JOB_TYPE,
        payload=plan.to_payload(),
        context={"project_id": project_id},
        subject_type="project",
        subject_id=project_id,
    )
    await background_service.commit_and_notify(session)
    return _to_response(job)


@router.get(
    "/projects/{project_id}/chapter-exports/{job_id}",
    response_model=ChapterExportResponse,
    summary="获取章节导出状态",
)
async def get_chapter_export(
    project_id: str,
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterExportResponse:
    job = await _get_export_job(session, project_id, job_id)
    return _to_response(job)


@router.post(
    "/projects/{project_id}/chapter-exports/{job_id}/cancel",
    response_model=ChapterExportResponse,
    summary="取消章节导出",
)
async def cancel_chapter_export(
    project_id: str,
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterExportResponse:
    job = await _get_export_job(session, project_id, job_id)
    job = await background_service.cancel_job(
        session,
        get_background_supervisor().create_event_publisher(),
        job,
        reason="用户取消导出",
    )
    await background_service.commit_and_notify(session)
    get_background_supervisor().cancel_running_chapter_export(job.id)
    return _to_response(job)


@router.get(
    "/projects/{project_id}/chapter-exports/{job_id}/download",
    summary="下载章节导出文件",
)
async def download_chapter_export(
    project_id: str,
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FileResponse:
    job = await _get_export_job(session, project_id, job_id)
    if not chapter_export_service.is_export_download_available(job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="导出文件不可用或已过期")
    _part_path, output_path = chapter_export_service.export_file_paths(job.id)
    return FileResponse(
        output_path,
        media_type="text/plain; charset=utf-8",
        filename=str(chapter_export_service.get_export_summary(job)["filename"]),
    )


async def _get_export_job(session: AsyncSession, project_id: str, job_id: str):
    job = await background_service.get_job(session, job_id)
    if (
        job is None
        or job.type != chapter_export_service.EXPORT_JOB_TYPE
        or job.subject_type != "project"
        or job.subject_id != project_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节导出任务不存在")
    return job


def _to_response(job) -> ChapterExportResponse:
    summary = chapter_export_service.get_export_summary(job)
    if chapter_export_service.is_export_download_available(job):
        summary["download_url"] = (
            f"/api/v1/projects/{job.subject_id}/chapter-exports/{job.id}/download"
        )
    return ChapterExportResponse.model_validate(summary)
