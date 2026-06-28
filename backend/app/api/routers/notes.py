# -*- coding: utf-8 -*-
"""
Notes Router - 笔记与分类 CRUD API。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.chapter import (
    MentionCandidateItem,
    MentionCandidateSearchResponse,
)
from app.api.schemas.note import (
    NoteCategoryCreate,
    NoteCategoryItem,
    NoteCategoryResponse,
    NoteCategoryUpdate,
    NoteCreate,
    NoteHiddenToggle,
    NoteItemMove,
    NoteListItem,
    NoteLockToggle,
    NoteMoveResult,
    NoteResponse,
    NoteSearchMatch,
    NoteSearchResponse,
    NoteSearchResult,
    NoteTreeResponse,
    NoteUpdate,
)
from app.background.jobs import service as background_service
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import note_service, mention_service

router = APIRouter(tags=["notes"])


def _build_category_item(node) -> NoteCategoryItem:
    return NoteCategoryItem(
        id=node.category.id,
        project_id=node.category.project_id,
        parent_id=node.category.parent_id,
        title=node.category.title,
        created_at=node.category.created_at,
        updated_at=node.category.updated_at,
        categories=[_build_category_item(child) for child in node.sub_categories],
        notes=[NoteListItem.model_validate(note) for note in node.notes],
    )


@router.post(
    "/projects/{project_id}/note-categories",
    response_model=NoteCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建笔记分类",
)
async def create_category(
    project_id: str,
    data: NoteCategoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteCategoryResponse:
    try:
        logger.info(f"创建笔记分类: project_id={project_id}, title={data.title}")
        category = await note_service.create_category(
            session,
            project_id=project_id,
            parent_id=data.parent_id,
            title=data.title,
        )
        await background_service.commit_and_notify(session)
        return NoteCategoryResponse.model_validate(category)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/note-categories/{category_id}",
    response_model=NoteCategoryResponse,
    summary="更新笔记分类",
)
async def update_category(
    category_id: str,
    data: NoteCategoryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteCategoryResponse:
    try:
        logger.info(f"更新笔记分类: {category_id}")
        category = await note_service.update_category(
            session, category_id, title=data.title
        )
        await background_service.commit_and_notify(session)
        return NoteCategoryResponse.model_validate(category)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/note-categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除笔记分类",
)
async def delete_category(
    category_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        logger.info(f"删除笔记分类: {category_id}")
        await note_service.delete_category(session, category_id)
        await background_service.commit_and_notify(session)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/note-items/move",
    response_model=NoteMoveResult,
    status_code=status.HTTP_200_OK,
    summary="移动分类或笔记",
)
async def move_item(
    data: NoteItemMove,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteMoveResult:
    try:
        logger.info(f"移动: kind={data.kind}, item_id={data.item_id}")
        result = await note_service.move_item(
            session,
            item_kind=data.kind,
            item_id=data.item_id,
            target_category_id=data.target_category_id,
        )
        await background_service.commit_and_notify(session)
        if data.kind == "note":
            return NoteMoveResult(
                kind="note",
                note=NoteResponse.model_validate(result),
            )
        else:
            return NoteMoveResult(
                kind="category",
                category=NoteCategoryResponse.model_validate(result),
            )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/projects/{project_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建笔记",
)
async def create_note(
    project_id: str,
    data: NoteCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteResponse:
    try:
        logger.info(f"创建笔记: project_id={project_id}, title={data.title}")
        note = await note_service.create_note(
            session,
            project_id=project_id,
            category_id=data.category_id,
            title=data.title,
            content=data.content,
        )
        await background_service.commit_and_notify(session)
        return NoteResponse.model_validate(note)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/projects/{project_id}/notes",
    response_model=NoteTreeResponse,
    summary="获取笔记列表",
)
async def list_notes(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteTreeResponse:
    try:
        result = await note_service.list_notes(session, project_id)
        return NoteTreeResponse(
            categories=[_build_category_item(node) for node in result.categories],
            root_notes=[NoteListItem.model_validate(n) for n in result.root_notes],
            total_notes=result.total_notes,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/notes/{note_id}",
    response_model=NoteResponse,
    summary="获取笔记详情",
)
async def get_note(
    note_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteResponse:
    try:
        note = await note_service.get_note(session, note_id)
        return NoteResponse.model_validate(note)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/notes/{note_id}",
    response_model=NoteResponse,
    summary="更新笔记",
)
async def update_note(
    note_id: str,
    data: NoteUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteResponse:
    try:
        logger.info(f"更新笔记: {note_id}")
        note = await note_service.update_note(
            session,
            note_id,
            title=data.title,
            content=data.content,
        )
        await background_service.commit_and_notify(session)
        return NoteResponse.model_validate(note)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除笔记",
)
async def delete_note(
    note_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        logger.info(f"删除笔记: {note_id}")
        await note_service.delete_note(session, note_id)
        await background_service.commit_and_notify(session)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/notes/{note_id}/lock",
    response_model=NoteResponse,
    summary="切换笔记锁定状态",
)
async def toggle_note_lock(
    note_id: str,
    data: NoteLockToggle,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteResponse:
    try:
        note = await note_service.set_note_locked(session, note_id, data.is_locked)
        await background_service.commit_and_notify(session)
        return NoteResponse.model_validate(note)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/notes/{note_id}/hidden",
    response_model=NoteResponse,
    summary="切换笔记隐藏状态",
)
async def toggle_note_hidden(
    note_id: str,
    data: NoteHiddenToggle,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteResponse:
    try:
        note = await note_service.set_note_hidden(session, note_id, data.is_hidden)
        await background_service.commit_and_notify(session)
        return NoteResponse.model_validate(note)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/mentions",
    response_model=MentionCandidateSearchResponse,
    summary="检索可添加到对话的 mention 候选项",
)
async def search_mention_candidates(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str, Query(description="mention 检索词")] = "",
    limit: Annotated[int, Query(ge=1, le=50, description="返回的最大候选数")] = 20,
    kind: Annotated[
        Literal["volume", "chapter", "note", "note_category"] | None,
        Query(description="候选类型过滤"),
    ] = None,
) -> MentionCandidateSearchResponse:
    try:
        items = await mention_service.search_all_mention_candidates(
            session,
            project_id,
            query,
            limit=limit,
            kind=kind,
        )
        return MentionCandidateSearchResponse(
            items=[
                MentionCandidateItem(
                    kind=item.kind,
                    id=item.id,
                    title=item.title,
                    label=item.label,
                    description=item.description,
                )
                for item in items
            ]
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/notes/search",
    response_model=NoteSearchResponse,
    summary="搜索笔记内容",
)
async def search_notes(
    project_id: str,
    q: Annotated[str, Query(description="搜索关键词")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteSearchResponse:
    """按内容搜索笔记，返回匹配的笔记及匹配行。"""
    try:
        result = await note_service.search_notes(session, project_id, q)
        return NoteSearchResponse(
            results=[
                NoteSearchResult(
                    note_id=r.note_id,
                    note_title=r.note_title,
                    category_path=r.category_path,
                    matches=[
                        NoteSearchMatch(
                            line_number=m.line_number, line_text=m.line_text
                        )
                        for m in r.matches
                    ],
                )
                for r in result.results
            ],
            total_notes=result.total_notes,
            total_matches=result.total_matches,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
