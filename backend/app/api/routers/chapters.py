# -*- coding: utf-8 -*-
"""
Chapters Router - 章节 CRUD API。
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
    summary="创建章节",
)
async def create_chapter(
    project_id: str,
    data: ChapterCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """
    在指定项目下创建新章节。

    Args:
        project_id: 项目 ID。
        data: 章节创建数据。
        session: 数据库 session。

    Returns:
        创建的章节。
    """
    try:
        logger.info(f"创建章节: project_id={project_id}, title={data.title}")
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


@router.get(
    "/projects/{project_id}/chapters",
    response_model=VolumeTreeResponse,
    summary="获取章节列表",
)
async def list_chapters(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolumeTreeResponse:
    """
    获取指定项目下的所有章节列表（精简版，不含正文）。

    Args:
        project_id: 项目 ID。
        session: 数据库 session。

    Returns:
        章节列表（精简版）。
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
    summary="获取章节详情",
)
async def get_chapter(
    chapter_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """
    获取单个章节的详细信息。

    Args:
        chapter_id: 章节 ID。
        session: 数据库 session。

    Returns:
        章节详情。

    Raises:
        HTTPException: 章节不存在时返回 404。
    """
    try:
        chapter = await chapter_service.get_chapter(session, chapter_id)
        return ChapterResponse.model_validate(chapter)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/chapters/{chapter_id}",
    response_model=ChapterResponse,
    summary="更新章节",
)
async def update_chapter(
    chapter_id: str,
    data: ChapterUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """
    更新章节信息。

    Args:
        chapter_id: 章节 ID。
        data: 更新数据。
        session: 数据库 session。

    Returns:
        更新后的章节。

    Raises:
        HTTPException: 章节不存在时返回 404。
    """
    try:
        logger.info(f"更新章节: {chapter_id}")
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


@router.delete(
    "/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除章节",
)
async def delete_chapter(
    chapter_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    删除章节。

    Args:
        chapter_id: 章节 ID。
        session: 数据库 session。

    Raises:
        HTTPException: 章节不存在时返回 404。
    """
    try:
        logger.info(f"删除章节: {chapter_id}")
        await chapter_service.delete_chapter(session, chapter_id)
        await background_service.commit_and_notify(session)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/chapters/reorder",
    response_model=list[ChapterListItem],
    summary="批量重排章节顺序",
)
async def reorder_chapters(
    data: ChapterReorder,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ChapterListItem]:
    """
    批量重排卷内章节顺序。

    Args:
        data: 重排数据（卷 ID + 按新顺序排列的章节 ID 列表）。
        session: 数据库 session。

    Returns:
        更新后的章节列表。

    Raises:
        HTTPException: 章节不存在或不属于指定卷时返回 400。
    """
    try:
        logger.info(
            f"批量重排章节: volume_id={data.volume_id}, chapter_ids={data.chapter_ids}"
        )
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
    summary="搜索章节内容",
)
async def search_chapters(
    project_id: str,
    q: Annotated[str, Query(description="搜索关键词")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterSearchResponse:
    """按内容搜索章节，返回匹配的章节及匹配行。"""
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
    summary="移动章节到卷",
)
async def move_chapter_to_volume(
    chapter_id: str,
    data: ChapterMoveToVolume,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChapterResponse:
    """跨卷移动章节，追加到目标卷末尾。"""
    try:
        logger.info(f"移动章节到卷: {chapter_id} -> volume={data.volume_id}")
        chapter = await chapter_service.move_chapter_to_volume(
            session,
            chapter_id=chapter_id,
            volume_id=data.volume_id,
        )
        await background_service.commit_and_notify(session)
        return ChapterResponse.model_validate(chapter)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
