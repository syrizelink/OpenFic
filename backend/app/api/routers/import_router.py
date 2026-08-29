# -*- coding: utf-8 -*-
"""
Import Router - 项目文件导入 API。
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.import_schema import (
    ImportConfirmResponse,
    ImportPreviewResponse,
    PreviewChapter,
    PreviewVolume,
)
from app.core.project_import import (
    DEFAULT_IMPORT_CHUNK_SIZE,
    MAX_IMPORT_CHUNK_SIZE,
    MAX_IMPORT_FILE_SIZE,
    ImportSplitMode,
    is_supported_import_file,
    parse_project_import,
)
from app.core.txt_parser import ParseResult
from app.storage.database import get_session
from app.storage.services import import_service

router = APIRouter(prefix="/import", tags=["import"])

SUPPORTED_FILE_DETAIL = "仅支持 .txt、.md 或 .zip 文件"


def _require_supported_filename(filename: str | None) -> str:
    if not is_supported_import_file(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SUPPORTED_FILE_DETAIL,
        )
    return filename or ""


async def _read_import_content(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_IMPORT_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小超过限制（最大 50MB）",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空",
        )
    return content


def _to_preview_response(result: ParseResult) -> ImportPreviewResponse:
    preview_volumes = [
        PreviewVolume(
            title=volume.title,
            chapter_count=len(volume.chapters),
            chapters=[
                PreviewChapter(
                    title=chapter.title,
                    word_count=chapter.word_count,
                    content_preview=chapter.content[:200] if chapter.content else "",
                )
                for chapter in volume.chapters
            ],
        )
        for volume in result.volumes
    ]
    return ImportPreviewResponse(
        volumes=preview_volumes,
        total_word_count=result.total_word_count,
        chapter_count=result.chapter_count,
        detected_encoding=result.detected_encoding,
    )


def _no_chapters_detail(filename: str) -> str:
    if filename.lower().endswith(".zip"):
        return "压缩包内未找到 TXT 或 Markdown 文件"
    return "文件解析失败，未能识别任何章节"


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    summary="预览项目导入文件",
)
async def preview_import_file(
    file: Annotated[UploadFile, File(description="TXT、Markdown 或 ZIP 文件")],
    split_mode: Annotated[ImportSplitMode, Form(description="分割模式")] = "auto",
    chunk_size: Annotated[
        int,
        Form(
            ge=1,
            le=MAX_IMPORT_CHUNK_SIZE,
            description="手动分割时的每章字数",
        ),
    ] = DEFAULT_IMPORT_CHUNK_SIZE,
) -> ImportPreviewResponse:
    """
    上传项目文件并获取解析预览。

    Args:
        file: TXT、Markdown 或 ZIP 文件。

    Returns:
        解析预览结果。

    Raises:
        HTTPException: 文件格式不支持或解析失败时返回 400。
    """
    filename = _require_supported_filename(file.filename)
    content = await _read_import_content(file)
    logger.info(f"预览导入文件: {filename}, 大小: {len(content)} 字节")

    try:
        result = parse_project_import(
            filename,
            content,
            split_mode=split_mode,
            chunk_size=chunk_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not result.volumes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_no_chapters_detail(filename),
        )

    return _to_preview_response(result)


@router.post(
    "/confirm",
    response_model=ImportConfirmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="确认导入",
)
async def confirm_import(
    file: Annotated[UploadFile, File(description="TXT、Markdown 或 ZIP 文件")],
    title: Annotated[str, Form(description="书名")],
    description: Annotated[str | None, Form(description="简介")] = None,
    cover: Annotated[UploadFile | None, File(description="封面图片")] = None,
    split_mode: Annotated[ImportSplitMode, Form(description="分割模式")] = "auto",
    chunk_size: Annotated[
        int,
        Form(
            ge=1,
            le=MAX_IMPORT_CHUNK_SIZE,
            description="手动分割时的每章字数",
        ),
    ] = DEFAULT_IMPORT_CHUNK_SIZE,
    session: AsyncSession = Depends(get_session),
) -> ImportConfirmResponse:
    """
    确认导入，创建项目和所有章节。

    Args:
        file: TXT、Markdown 或 ZIP 文件。
        title: 书名。
        description: 简介（可选）。
        cover: 封面图片（可选）。
        session: 数据库 session。

    Returns:
        导入结果。

    Raises:
        HTTPException: 导入失败时返回错误。
    """
    filename = _require_supported_filename(file.filename)
    content = await _read_import_content(file)

    # 验证书名
    title = title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="书名不能为空",
        )

    logger.info(f"确认导入: {filename} -> {title}")

    # 解析文件
    try:
        parse_result = parse_project_import(
            filename,
            content,
            split_mode=split_mode,
            chunk_size=chunk_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not parse_result.volumes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_no_chapters_detail(filename),
        )

    # 调用服务层执行导入
    try:
        result = await import_service.confirm_import(
            session=session,
            title=title,
            description=description,
            cover_file=cover,
            volumes=parse_result.volumes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ImportConfirmResponse(
        project_id=result.project_id,
        title=result.title,
        chapter_count=result.chapter_count,
        total_word_count=result.total_word_count,
    )


@router.post(
    "/confirm-stream",
    summary="确认导入（流式进度）",
)
async def confirm_import_stream(
    file: Annotated[UploadFile, File(description="TXT、Markdown 或 ZIP 文件")],
    title: Annotated[str, Form(description="书名")],
    description: Annotated[str | None, Form(description="简介")] = None,
    cover: Annotated[UploadFile | None, File(description="封面图片")] = None,
    split_mode: Annotated[ImportSplitMode, Form(description="分割模式")] = "auto",
    chunk_size: Annotated[
        int,
        Form(
            ge=1,
            le=MAX_IMPORT_CHUNK_SIZE,
            description="手动分割时的每章字数",
        ),
    ] = DEFAULT_IMPORT_CHUNK_SIZE,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """
    确认导入，使用 SSE 流式返回进度。

    进度事件格式：
    - {"type": "progress", "stage": "parsing", "progress": 10}
    - {"type": "progress", "stage": "creating_project", "progress": 20}
    - {"type": "progress", "stage": "saving_chapters", "progress": 30, "current": 1, "total": 100}
    - {"type": "complete", "project_id": "xxx", "chapter_count": 100, "total_word_count": 123456}
    - {"type": "error", "message": "错误信息"}
    """

    async def generate_progress():
        try:
            filename = file.filename
            if not is_supported_import_file(filename):
                yield f"data: {json.dumps({'type': 'error', 'message': SUPPORTED_FILE_DETAIL})}\n\n"
                return

            # 进度：读取文件
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'reading', 'progress': 5})}\n\n"

            content = await file.read()

            if len(content) > MAX_IMPORT_FILE_SIZE:
                yield f"data: {json.dumps({'type': 'error', 'message': '文件大小超过限制（最大 50MB）'})}\n\n"
                return

            if len(content) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': '文件内容为空'})}\n\n"
                return

            title_clean = title.strip()
            if not title_clean:
                yield f"data: {json.dumps({'type': 'error', 'message': '书名不能为空'})}\n\n"
                return

            # 进度：解析文件
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'progress': 15})}\n\n"

            parse_result = parse_project_import(
                filename or "",
                content,
                split_mode=split_mode,
                chunk_size=chunk_size,
            )

            if not parse_result.volumes:
                yield f"data: {json.dumps({'type': 'error', 'message': _no_chapters_detail(filename or '')})}\n\n"
                return

            total_chapters = parse_result.chapter_count

            # 进度：创建项目
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'creating_project', 'progress': 25})}\n\n"

            # 调用服务层执行导入
            result = await import_service.confirm_import(
                session=session,
                title=title_clean,
                description=description,
                cover_file=cover,
                volumes=parse_result.volumes,
            )

            # 进度：保存章节（模拟进度，实际已在批量插入中完成）
            for i in range(0, total_chapters, max(1, total_chapters // 10)):
                progress = 30 + int((i / total_chapters) * 65)
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'saving_chapters', 'progress': progress, 'current': i + 1, 'total': total_chapters})}\n\n"

            # 完成
            yield f"data: {json.dumps({'type': 'complete', 'project_id': result.project_id, 'title': result.title, 'chapter_count': result.chapter_count, 'total_word_count': result.total_word_count})}\n\n"

        except Exception as e:
            logger.exception(f"导入失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
