# -*- coding: utf-8 -*-
"""
Chapters Router - API CRUD bab.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.chapter import (
    ChapterCreate,
    ChapterListItem,
    ChapterMoveToVolume,
    ChapterReorder,
    ChapterResponse,
    ChapterSearchMatch,
    ChapterSearchResponse,
    ChapterSearchResult,
    ChapterUpdate,
    VolumeTreeItem,
    VolumeTreeResponse,
)
from app.background.jobs import service as background_service
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import chapter_service

router = APIRouter(tags=["chapters"])


@router.post(
    "/projects/{project_id}/chapters",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat bab",
)
async def create_chapter(
    project_id: str,
    data: ChapterCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """
    Membuat bab baru pada proyek tertentu.

    Args:
        project_id: ID proyek.
        data: Data pembuatan bab.
        session: Session basis data.

    Returns:
        Bab yang dibuat.
    """
    try:
        logger.info(f"Membuat bab: project_id={project_id}, title={data.title}")
        chapter = await chapter_service.create_chapter(
            session,
            project_id=project_id,
            volume_id=data.volume_id,
            title=data.title,
            content=data.content,
            word_count=data.word_count,
        )
        await background_service.commit_and_notify(session)
        return ChapterResponse.model_validate(chapter)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/projects/{project_id}/chapters",
    response_model=VolumeTreeResponse,
    summary="Mengambil daftar bab",
)
async def list_chapters(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeTreeResponse:
    """
    Mengambil semua daftar bab pada proyek tertentu (versi ringkas, tanpa isi).

    Args:
        project_id: ID proyek.
        session: Session basis data.

    Returns:
        Daftar bab (versi ringkas).
    """
    try:
        result = await chapter_service.list_chapters(session, project_id)
        return VolumeTreeResponse(
            volumes=[
                VolumeTreeItem(
                    **group.volume.model_dump(),
                    chapters=[
                        ChapterListItem.model_validate(chapter)
                        for chapter in group.chapters
                    ],
                )
                for group in result.volumes
            ],
            total_chapters=result.total_chapters,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/chapters/{chapter_id}",
    response_model=ChapterResponse,
    summary="Mengambil detail bab",
)
async def get_chapter(
    chapter_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """
    Mengambil informasi detail satu bab.

    Args:
        chapter_id: ID bab.
        session: Session basis data.

    Returns:
        Detail bab.

    Raises:
        HTTPException: Mengembalikan 404 bila bab tidak ditemukan.
    """
    try:
        chapter = await chapter_service.get_chapter(session, chapter_id)
        return ChapterResponse.model_validate(chapter)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/chapters/{chapter_id}",
    response_model=ChapterResponse,
    summary="Memperbarui bab",
)
async def update_chapter(
    chapter_id: str,
    data: ChapterUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """
    Memperbarui informasi bab.

    Args:
        chapter_id: ID bab.
        data: Data pembaruan.
        session: Session basis data.

    Returns:
        Bab setelah diperbarui.

    Raises:
        HTTPException: Mengembalikan 404 bila bab tidak ditemukan.
    """
    try:
        logger.info(f"Memperbarui bab: {chapter_id}")
        chapter = await chapter_service.update_chapter(
            session,
            chapter_id,
            title=data.title,
            content=data.content,
            word_count=data.word_count,
        )
        await background_service.commit_and_notify(session)
        return ChapterResponse.model_validate(chapter)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Menghapus bab",
)
async def delete_chapter(
    chapter_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    Menghapus bab.

    Args:
        chapter_id: ID bab.
        session: Session basis data.

    Raises:
        HTTPException: Mengembalikan 404 bila bab tidak ditemukan.
    """
    try:
        logger.info(f"Menghapus bab: {chapter_id}")
        await chapter_service.delete_chapter(session, chapter_id)
        await background_service.commit_and_notify(session)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/chapters/reorder",
    response_model=list[ChapterListItem],
    summary="Menata ulang urutan bab secara massal",
)
async def reorder_chapters(
    data: ChapterReorder,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ChapterListItem]:
    """
    Menata ulang urutan bab di dalam volume secara massal.

    Args:
        data: Data penataan ulang (ID volume + daftar ID bab dalam urutan baru).
        session: Session basis data.

    Returns:
        Daftar bab setelah diperbarui.

    Raises:
        HTTPException: Mengembalikan 400 bila bab tidak ditemukan atau bukan milik volume tersebut.
    """
    try:
        chapters = await chapter_service.reorder_chapters(
            session, data.volume_id, data.chapter_ids
        )
        await background_service.commit_and_notify(session)
        return [ChapterListItem.model_validate(chapter) for chapter in chapters]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/chapters/search",
    response_model=ChapterSearchResponse,
    summary="Mencari isi bab",
)
async def search_chapters(
    project_id: str,
    q: Annotated[str, Query(description="Kata kunci pencarian")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterSearchResponse:
    """Mencari bab berdasarkan isi, mengembalikan bab yang cocok beserta baris yang cocok."""
    try:
        result = await chapter_service.search_chapters(session, project_id, q)
        return ChapterSearchResponse(
            results=[
                ChapterSearchResult(
                    chapter_id=r.chapter_id,
                    chapter_title=r.chapter_title,
                    volume_title=r.volume_title,
                    matches=[
                        ChapterSearchMatch(
                            line_number=m.line_number, line_text=m.line_text
                        )
                        for m in r.matches
                    ],
                )
                for r in result.results
            ],
            total_chapters=result.total_chapters,
            total_matches=result.total_matches,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/chapters/{chapter_id}/move-to-volume",
    response_model=ChapterResponse,
    summary="Memindahkan bab ke volume",
)
async def move_chapter_to_volume(
    chapter_id: str,
    data: ChapterMoveToVolume,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """Memindahkan bab antar volume, ditambahkan ke akhir volume tujuan."""
    try:
        logger.info(f"Memindahkan bab ke volume: {chapter_id} -> volume={data.volume_id}")
        chapter = await chapter_service.move_chapter_to_volume(
            session,
            chapter_id=chapter_id,
            volume_id=data.volume_id,
        )
        await background_service.commit_and_notify(session)
        return ChapterResponse.model_validate(chapter)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
