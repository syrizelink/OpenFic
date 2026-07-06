# -*- coding: utf-8 -*-
"""Character Router - 角色 CRUD API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.character import (
    CharacterBatchDeleteRequest,
    CharacterBatchDeleteResponse,
    CharacterBatchFavoriteRequest,
    CharacterBatchFavoriteResponse,
    CharacterListItemResponse,
    CharacterListResponse,
    CharacterResponse,
    CharacterSearchMatch,
    CharacterSearchResponse,
    CharacterSearchResult,
)
from app.core.errors import ConflictError, NotFoundError
from app.core.storage import get_character_image_url
from app.storage.database import get_session
from app.storage.models.character import Character
from app.storage.services import character_service

router = APIRouter(tags=["characters"])


def to_response(character: Character) -> CharacterResponse:
    """转换角色响应。"""
    return CharacterResponse(
        id=character.id,
        project_id=character.project_id,
        name=character.name,
        description=character.description,
        image_url=get_character_image_url(character.image_path),
        is_favorited=character.is_favorited,
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


def to_list_item_response(character: Character) -> CharacterListItemResponse:
    """转换角色列表项响应。"""
    return CharacterListItemResponse(
        id=character.id,
        project_id=character.project_id,
        name=character.name,
        image_url=get_character_image_url(character.image_path),
        token_count=character_service.calculate_token_count(character.description),
        is_favorited=character.is_favorited,
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


@router.get(
    "/projects/{project_id}/characters",
    response_model=CharacterListResponse,
    summary="获取项目角色列表",
)
async def list_project_characters(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 50,
) -> CharacterListResponse:
    """获取项目角色列表。"""
    try:
        result = await character_service.list_characters_by_project(
            session, project_id, page=page, page_size=page_size
        )
        return CharacterListResponse(
            items=[to_list_item_response(character) for character in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/projects/{project_id}/characters",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建角色",
)
async def create_character(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    description: Annotated[str, Form()] = "",
    image: Annotated[UploadFile | None, File()] = None,
) -> CharacterResponse:
    """创建角色。"""
    try:
        logger.info(f"创建角色: project_id={project_id}, name={name}")
        character = await character_service.create_character(
            session, project_id, name=name, description=description, image_file=image
        )
        return to_response(character)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/projects/{project_id}/characters/search",
    response_model=CharacterSearchResponse,
    summary="搜索项目角色",
)
async def search_project_characters(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str, Query(min_length=1, description="搜索关键词")],
) -> CharacterSearchResponse:
    """搜索项目角色名称和描述。"""
    try:
        result = await character_service.search_characters(session, project_id, q)
        return CharacterSearchResponse(
            results=[
                CharacterSearchResult(
                    character_id=item.character_id,
                    character_name=item.character_name,
                    matches=[
                        CharacterSearchMatch(
                            line_number=match.line_number,
                            line_text=match.line_text,
                        )
                        for match in item.matches
                    ],
                )
                for item in result.results
            ],
            total_characters=result.total_characters,
            total_matches=result.total_matches,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/projects/{project_id}/characters/batch/favorite",
    response_model=CharacterBatchFavoriteResponse,
    summary="批量更新角色收藏状态",
)
async def batch_favorite_characters(
    project_id: str,
    data: CharacterBatchFavoriteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterBatchFavoriteResponse:
    """批量更新项目内角色收藏状态。"""
    try:
        logger.info(f"批量更新角色收藏: project_id={project_id}, count={len(data.character_ids)}")
        updated_count = await character_service.batch_update_favorite(
            session, project_id, data.character_ids, data.is_favorited
        )
        return CharacterBatchFavoriteResponse(updated_count=updated_count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/projects/{project_id}/characters/batch/delete",
    response_model=CharacterBatchDeleteResponse,
    summary="批量删除角色",
)
async def batch_delete_characters(
    project_id: str,
    data: CharacterBatchDeleteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterBatchDeleteResponse:
    """批量删除项目内角色。"""
    try:
        logger.info(f"批量删除角色: project_id={project_id}, count={len(data.character_ids)}")
        deleted_count = await character_service.batch_delete_characters(
            session, project_id, data.character_ids
        )
        return CharacterBatchDeleteResponse(deleted_count=deleted_count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/characters/{character_id}",
    response_model=CharacterResponse,
    summary="获取角色",
)
async def get_character(
    character_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterResponse:
    """获取角色。"""
    try:
        character = await character_service.get_character(session, character_id)
        return to_response(character)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/characters/{character_id}",
    response_model=CharacterResponse,
    summary="更新角色",
)
async def update_character(
    character_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    name: Annotated[str | None, Form(min_length=1, max_length=200)] = None,
    description: Annotated[str | None, Form()] = None,
    is_favorited: Annotated[bool | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> CharacterResponse:
    """更新角色。"""
    try:
        character = await character_service.update_character(
            session,
            character_id,
            name=name,
            description=description,
            is_favorited=is_favorited,
            image_file=image,
        )
        return to_response(character)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete(
    "/characters/{character_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除角色",
)
async def delete_character(
    character_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """删除角色。"""
    try:
        await character_service.delete_character(session, character_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
