# -*- coding: utf-8 -*-
"""
Projects Router - API CRUD proyek.
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
    summary="Membuat proyek",
)
async def create_project(
    title: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """
    Membuat proyek novel baru.

    Args:
        title: Judul proyek.
        description: Sinopsis proyek (opsional).
        cover: Gambar sampul (opsional).
        session: Session basis data.

    Returns:
        Proyek yang dibuat.
    """
    logger.info(f"Membuat proyek: {title}")
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
    summary="Mengambil daftar proyek",
)
async def list_projects(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1, description="Nomor halaman")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Jumlah per halaman")] = 20,
    search: Annotated[str | None, Query(description="Cari berdasarkan judul atau sinopsis proyek")] = None,
    sort_by: Annotated[
        Literal["updated_at", "created_at", "title"],
        Query(description="Field pengurutan"),
    ] = "updated_at",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(description="Arah pengurutan")
    ] = "desc",
) -> ProjectListResponse:
    """
    Mengambil daftar proyek dengan dukungan paginasi.

    Args:
        session: Session basis data.
        page: Nomor halaman, mulai dari 1.
        page_size: Jumlah per halaman, maksimum 100.
        search: Kata pencarian judul atau sinopsis proyek.
        sort_by: Field pengurutan, pilihan updated_at, created_at, title.
        sort_order: Arah pengurutan, pilihan asc, desc.

    Returns:
        Daftar proyek.
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
    summary="Mengambil detail proyek",
)
async def get_project(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    """
    Mengambil informasi detail satu proyek.

    Args:
        project_id: ID proyek.
        session: Session basis data.

    Returns:
        Detail proyek.

    Raises:
        HTTPException: Mengembalikan 404 bila proyek tidak ditemukan.
    """
    try:
        project = await project_service.get_project(session, project_id)
        return _project_to_response(project)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Memperbarui proyek",
)
async def update_project(
    project_id: str,
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """
    Memperbarui informasi proyek.

    Args:
        project_id: ID proyek.
        title: Judul baru (opsional).
        description: Sinopsis baru (opsional).
        cover: Gambar sampul baru (opsional).
        session: Session basis data.

    Returns:
        Proyek setelah diperbarui.

    Raises:
        HTTPException: Mengembalikan 404 bila proyek tidak ditemukan.
    """
    try:
        logger.info(f"Memperbarui proyek: {project_id}")
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
    summary="Menghapus proyek",
)
async def delete_project(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    Menghapus proyek.

    Args:
        project_id: ID proyek.
        session: Session basis data.

    Raises:
        HTTPException: Mengembalikan 404 bila proyek tidak ditemukan.
    """
    try:
        logger.info(f"Menghapus proyek: {project_id}")
        tasks = (await task_service.list_tasks(session, project_id)).items
        if any(task.is_running for task in tasks):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Proyek memiliki tugas yang sedang berjalan, tidak dapat dihapus",
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
    Mengonversi model Project menjadi ProjectResponse, menambahkan cover_url.

    Args:
        project: Instance model Project.

    Returns:
        ProjectResponse.
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
