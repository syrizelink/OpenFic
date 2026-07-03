# -*- coding: utf-8 -*-
"""
WorldInfo Entries Router - 世界书条目 CRUD API。
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.world_info import (
    WorldInfoEntryBatchDeleteRequest,
    WorldInfoEntryBatchDeleteResponse,
    WorldInfoEntryBatchToggleRequest,
    WorldInfoEntryBatchToggleResponse,
    WorldInfoEntryBriefListResponse,
    WorldInfoEntryBriefResponse,
    WorldInfoEntryCreate,
    WorldInfoEntryMoveRequest,
    WorldInfoEntryReorderRequest,
    WorldInfoEntryResponse,
    WorldInfoEntrySearchMatch,
    WorldInfoEntrySearchResponse,
    WorldInfoEntrySearchResult,
    WorldInfoImportPreviewEntry,
    WorldInfoImportPreviewResponse,
    WorldInfoEntryUpdate,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import world_info_entry_service

router = APIRouter(tags=["world-info"])

MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024


def _entry_to_response(entry) -> WorldInfoEntryResponse:
    """
    将 WorldInfoEntry 模型转换为响应模型。

    Args:
        entry: WorldInfoEntry 模型实例。

    Returns:
        WorldInfoEntryResponse。
    """
    return WorldInfoEntryResponse(
        id=entry.id,
        world_info_id=entry.world_info_id,
        uid=entry.uid,
        name=entry.name,
        order=entry.order,
        content=entry.content,
        token_count=entry.token_count,
        is_enabled=entry.is_enabled,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _preview_entry_to_response(
    entry: world_info_entry_service.WorldInfoImportEntry,
) -> WorldInfoImportPreviewEntry:
    """将导入预览条目转换为响应模型。"""
    return WorldInfoImportPreviewEntry(
        uid=entry.uid,
        name=entry.name,
        content_preview=entry.content[:200],
        is_enabled=entry.is_enabled,
    )


def _entry_to_brief_response(entry) -> WorldInfoEntryBriefResponse:
    """将 WorldInfoEntry 模型转换为轻量响应模型（不含 content）。"""
    return WorldInfoEntryBriefResponse(
        id=entry.id,
        world_info_id=entry.world_info_id,
        uid=entry.uid,
        name=entry.name,
        order=entry.order,
        token_count=entry.token_count,
        is_enabled=entry.is_enabled,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ============== 世界书条目端点 ==============


@router.post(
    "/world-info/import/preview",
    response_model=WorldInfoImportPreviewResponse,
    summary="预览世界书导入",
)
async def preview_world_info_import(
    file: Annotated[UploadFile, File(description="SillyTavern 世界书 JSON 文件")],
) -> WorldInfoImportPreviewResponse:
    """预览 SillyTavern 世界书导入结果。"""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .json 文件",
        )

    content = await file.read()
    if len(content) > MAX_IMPORT_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小超过限制（最大 10MB）",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空",
        )

    try:
        preview = world_info_entry_service.parse_sillytavern_worldbook(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return WorldInfoImportPreviewResponse(
        entry_count=len(preview.entries),
        enabled_count=sum(1 for entry in preview.entries if entry.is_enabled),
        entries=[_preview_entry_to_response(entry) for entry in preview.entries],
    )


@router.post(
    "/world-info/{world_info_id}/entries/import-stream",
    response_model=None,
    summary="流式导入世界书条目",
)
async def import_entries_stream(
    world_info_id: str,
    file: Annotated[UploadFile, File(description="SillyTavern 世界书 JSON 文件")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    """流式导入世界书条目并返回实时进度。"""

    async def generate_progress():
        try:
            if not file.filename or not file.filename.lower().endswith(".json"):
                yield f"data: {json.dumps({'type': 'error', 'message': '仅支持 .json 文件'}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'reading', 'progress': 5}, ensure_ascii=False)}\n\n"
            content = await file.read()

            if len(content) > MAX_IMPORT_FILE_SIZE:
                yield f"data: {json.dumps({'type': 'error', 'message': '文件大小超过限制（最大 10MB）'}, ensure_ascii=False)}\n\n"
                return
            if len(content) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': '文件内容为空'}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'progress': 20}, ensure_ascii=False)}\n\n"
            preview = world_info_entry_service.parse_sillytavern_worldbook(content)
            total_entries = len(preview.entries)

            for index in range(total_entries):
                progress = 35 + int(((index + 1) / total_entries) * 60)
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'importing_entries', 'progress': progress, 'current': index + 1, 'total': total_entries}, ensure_ascii=False)}\n\n"

            result = await world_info_entry_service.import_entries(
                session=session,
                world_info_id=world_info_id,
                entries=preview.entries,
            )

            complete_event = {
                "type": "complete",
                "world_info_id": result.world_info_id,
                "imported_count": result.imported_count,
            }
            yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"
        except NotFoundError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception(f"导入世界书失败: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/world-info/{world_info_id}/entries",
    response_model=WorldInfoEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建条目",
)
async def create_entry(
    world_info_id: str,
    data: WorldInfoEntryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    创建世界书条目。

    Args:
        world_info_id: 世界书 ID。
        data: 创建请求数据。
        session: 数据库 session。

    Returns:
        创建的条目。

    Raises:
        HTTPException: 世界书不存在。
    """
    try:
        logger.info(f"创建条目: world_info_id={world_info_id}, name={data.name}")
        entry = await world_info_entry_service.create_entry(
            session,
            world_info_id,
            name=data.name,
            content=data.content,
            token_count=data.token_count,
            is_enabled=data.is_enabled,
        )
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/world-info/{world_info_id}/entries",
    response_model=WorldInfoEntryBriefListResponse,
    summary="获取条目列表",
)
async def list_entries(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=500, description="每页数量")] = 100,
) -> WorldInfoEntryBriefListResponse:
    """
    获取世界书的条目列表（轻量，不含 content）。

    Args:
        world_info_id: 世界书 ID。
        session: 数据库 session。
        page: 页码。
        page_size: 每页数量。

    Returns:
        条目轻量列表。

    Raises:
        HTTPException: 世界书不存在。
    """
    try:
        result = await world_info_entry_service.list_entries(
            session, world_info_id, page=page, page_size=page_size
        )
        return WorldInfoEntryBriefListResponse(
            items=[_entry_to_brief_response(e) for e in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/world-info-entries/{entry_id}",
    response_model=WorldInfoEntryResponse,
    summary="获取条目详情",
)
async def get_entry(
    entry_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    获取单个条目详情。

    Args:
        entry_id: 条目 ID。
        session: 数据库 session。

    Returns:
        条目详情。

    Raises:
        HTTPException: 条目不存在。
    """
    try:
        entry = await world_info_entry_service.get_entry(session, entry_id)
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/world-info-entries/{entry_id}",
    response_model=WorldInfoEntryResponse,
    summary="更新条目",
)
async def update_entry(
    entry_id: str,
    data: WorldInfoEntryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    更新世界书条目。

    Args:
        entry_id: 条目 ID。
        data: 更新请求数据。
        session: 数据库 session。

    Returns:
        更新后的条目。

    Raises:
        HTTPException: 条目不存在。
    """
    try:
        logger.info(f"更新条目: {entry_id}")
        entry = await world_info_entry_service.update_entry(
            session,
            entry_id,
            name=data.name,
            content=data.content,
            token_count=data.token_count,
            is_enabled=data.is_enabled,
        )
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except world_info_entry_service.WorldInfoEntryNameConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete(
    "/world-info/{world_info_id}/entries",
    status_code=status.HTTP_200_OK,
    summary="删除世界书的所有条目",
)
async def delete_all_entries(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int]:
    """
    删除世界书的所有条目。

    Args:
        world_info_id: 世界书 ID。
        session: 数据库 session。

    Returns:
        删除的条目数量。
    """
    try:
        logger.info(f"删除世界书所有条目: world_info_id={world_info_id}")
        deleted_count = await world_info_entry_service.delete_all_entries(
            session, world_info_id
        )
        return {"deleted_count": deleted_count}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/world-info-entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除条目",
)
async def delete_entry(
    entry_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    删除世界书条目。

    Args:
        entry_id: 条目 ID。
        session: 数据库 session。

    Raises:
        HTTPException: 条目不存在。
    """
    try:
        logger.info(f"删除条目: {entry_id}")
        await world_info_entry_service.delete_entry(session, entry_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/world-info-entries/{entry_id}/move",
    response_model=WorldInfoEntryResponse,
    summary="移动条目",
)
async def move_entry(
    entry_id: str,
    data: WorldInfoEntryMoveRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    移动世界书条目到新位置。

    Args:
        entry_id: 条目 ID。
        data: 移动请求数据。
        session: 数据库 session。

    Returns:
        移动后的条目。

    Raises:
        HTTPException: 条目不存在或位置无效。
    """
    try:
        logger.info(f"移动条目: {entry_id} -> order={data.new_order}")
        entry = await world_info_entry_service.move_entry(
            session, entry_id, data.new_order
        )
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/world-info/{world_info_id}/entries/reorder",
    response_model=list[WorldInfoEntryResponse],
    summary="批量重新排序条目",
)
async def reorder_entries(
    world_info_id: str,
    data: WorldInfoEntryReorderRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WorldInfoEntryResponse]:
    """
    批量重新排序世界书条目。

    Args:
        world_info_id: 世界书 ID。
        data: 重新排序请求数据，包含条目ID到新排序位置的映射。
        session: 数据库 session。

    Returns:
        更新后的条目列表，按新顺序排序。

    Raises:
        HTTPException: 条目不存在或排序位置无效。
    """
    try:
        logger.info(f"批量重新排序条目: world_info_id={world_info_id}, orders={data.orders}")
        entries = await world_info_entry_service.reorder_entries(
            session, world_info_id, data.orders
        )
        return [_entry_to_response(entry) for entry in entries]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/world-info-entries/{entry_id}/toggle",
    response_model=WorldInfoEntryResponse,
    summary="切换条目开关",
)
async def toggle_entry(
    entry_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    切换世界书条目的开关状态。

    Args:
        entry_id: 条目 ID。
        session: 数据库 session。

    Returns:
        切换后的条目。

    Raises:
        HTTPException: 条目不存在。
    """
    try:
        logger.info(f"切换条目开关: {entry_id}")
        entry = await world_info_entry_service.toggle_entry(session, entry_id)
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/world-info/{world_info_id}/entries/batch/toggle",
    response_model=WorldInfoEntryBatchToggleResponse,
    summary="批量切换条目开关",
)
async def batch_toggle_entries(
    world_info_id: str,
    data: WorldInfoEntryBatchToggleRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryBatchToggleResponse:
    """批量切换世界书条目的开关状态。"""
    try:
        logger.info(f"批量切换条目开关: world_info_id={world_info_id}, count={len(data.entry_ids)}")
        updated_count = await world_info_entry_service.batch_toggle_entries(
            session, world_info_id, data.entry_ids, data.is_enabled
        )
        return WorldInfoEntryBatchToggleResponse(updated_count=updated_count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/world-info/{world_info_id}/entries/batch/delete",
    response_model=WorldInfoEntryBatchDeleteResponse,
    summary="批量删除条目",
)
async def batch_delete_entries(
    world_info_id: str,
    data: WorldInfoEntryBatchDeleteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryBatchDeleteResponse:
    """批量删除世界书条目。"""
    try:
        logger.info(f"批量删除条目: world_info_id={world_info_id}, count={len(data.entry_ids)}")
        deleted_count = await world_info_entry_service.batch_delete_entries(
            session, world_info_id, data.entry_ids
        )
        return WorldInfoEntryBatchDeleteResponse(deleted_count=deleted_count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/world-info/{world_info_id}/entries/search",
    response_model=WorldInfoEntrySearchResponse,
    summary="搜索条目内容",
)
async def search_entries(
    world_info_id: str,
    q: Annotated[str, Query(min_length=1, description="搜索关键词")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntrySearchResponse:
    try:
        result = await world_info_entry_service.search_entries(
            session, world_info_id, q
        )
        return WorldInfoEntrySearchResponse(
            results=[
                WorldInfoEntrySearchResult(
                    entry_id=r.entry_id,
                    entry_name=r.entry_name,
                    uid=r.uid,
                    matches=[
                        WorldInfoEntrySearchMatch(
                            line_number=m.line_number,
                            line_text=m.line_text,
                        )
                        for m in r.matches
                    ],
                )
                for r in result.results
            ],
            total_entries=result.total_entries,
            total_matches=result.total_matches,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
