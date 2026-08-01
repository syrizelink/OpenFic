# -*- coding: utf-8 -*-
"""
Google Drive 整本同步编排。

- `schedule_project_sync`：章节/卷变更后标记项目为需要同步（由 API 挂接）。
- `sync_project`：组合整本书 HTML 并上传/更新 Google Doc（手动与自动共用）。
- `run_periodic_sync_check`：定时兜底，处理漏标或内容哈希变化的项目。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.google_drive import config as drive_config
from app.google_drive import oauth
from app.google_drive.client import DriveClient
from app.google_drive.errors import (
    DriveApiError,
    DriveAuthError,
    DriveError,
    DriveNotConnectedError,
)
from app.google_drive.html_builder import (
    BookChapter,
    BookVolume,
    build_book_html,
)
from app.storage.repos import chapter_repo, project_repo, volume_repo


class DriveNoContentError(DriveError):
    """项目还没有任何可同步的章节。"""


@dataclass(frozen=True)
class BookContent:
    """整本书组合结果。"""

    html: str
    name: str
    chapter_count: int
    word_count: int

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.html.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SyncResult:
    """一次同步的结果。"""

    status: str  # "synced" | "unchanged" | "error"
    project_id: str
    file_id: str | None = None
    doc_name: str | None = None
    doc_url: str | None = None
    chapter_count: int = 0
    word_count: int = 0
    synced_at: str | None = None
    message: str | None = None


_sync_locks: dict[str, asyncio.Lock] = {}


def _lock_for(project_id: str) -> asyncio.Lock:
    return _sync_locks.setdefault(project_id, asyncio.Lock())


async def schedule_project_sync(session: AsyncSession, project_id: str) -> None:
    """章节/卷变更后标记项目需要同步（幂等且便宜，不做网络调用）。"""
    if not await drive_config.is_project_sync_enabled(session, project_id):
        return
    await drive_config.set_project_dirty(session, project_id, True)


async def build_book_content(session: AsyncSession, project_id: str) -> BookContent:
    """读取项目全部章节并组合为单个 HTML。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise LookupError(f"项目不存在: {project_id}")

    volumes = await volume_repo.list_by_project(session, project_id)
    chapters = await chapter_repo.list_by_project(session, project_id)
    if not chapters:
        raise DriveNoContentError("项目还没有任何章节")

    project_title = project.title or "未命名项目"
    html_doc = build_book_html(
        project_title,
        [
            BookVolume(id=volume.id, title=volume.title or "未命名卷", order=volume.order)
            for volume in volumes
        ],
        [
            BookChapter(
                id=chapter.id,
                volume_id=chapter.volume_id,
                title=chapter.title or "未命名章节",
                content=chapter.content or "",
            )
            for chapter in chapters
        ],
    )
    word_count = sum(chapter.word_count for chapter in chapters)
    name = f"{project_title}{drive_config.DRIVE_DOC_SUFFIX}"
    return BookContent(
        html=html_doc,
        name=name,
        chapter_count=len(chapters),
        word_count=word_count,
    )


async def sync_project(
    session: AsyncSession,
    project_id: str,
    *,
    manual: bool = False,
) -> SyncResult:
    """同步一个项目到 Google Drive，返回结果。"""
    lock = _lock_for(project_id)
    async with lock:
        return await _sync_project_locked(session, project_id, manual=manual)


async def _sync_project_locked(
    session: AsyncSession,
    project_id: str,
    *,
    manual: bool,
) -> SyncResult:
    now_iso = datetime.now(UTC).isoformat()
    await drive_config.set_value(
        session, drive_config.SETTING_KEY_LAST_SYNC_ATTEMPT, now_iso
    )

    try:
        if not await drive_config.is_connected(session):
            raise DriveNotConnectedError("尚未连接 Google 账号")

        book = await build_book_content(session, project_id)
        stored_hash = await drive_config.get_project_hash(session, project_id)
        dirty = await drive_config.is_project_dirty(session, project_id)
        if not manual and stored_hash == book.content_hash and not dirty:
            return SyncResult(
                status="unchanged",
                project_id=project_id,
                chapter_count=book.chapter_count,
                word_count=book.word_count,
            )

        token = await oauth.get_access_token(session)
        client = DriveClient(token)
        try:
            result = await _upload_book(client, session, project_id, book)
        except DriveAuthError:
            token = await oauth.force_refresh_access_token(session)
            result = await _upload_book(DriveClient(token), session, project_id, book)

        await drive_config.set_project_file_id(session, project_id, result["file_id"])
        await drive_config.set_project_hash(session, project_id, book.content_hash)
        await drive_config.set_project_last_synced_at(session, project_id, now_iso)
        await drive_config.set_project_dirty(session, project_id, False)
        await drive_config.clear_project_error(session, project_id)
        if result["folder_id"]:
            await drive_config.set_value(
                session, drive_config.SETTING_KEY_DRIVE_FOLDER_ID, result["folder_id"]
            )

        logger.info(
            f"Google Drive 同步完成: project_id={project_id} "
            f"file_id={result['file_id']} chapters={book.chapter_count}"
        )
        return SyncResult(
            status="synced",
            project_id=project_id,
            file_id=result["file_id"],
            doc_name=book.name,
            doc_url=result["web_view_link"],
            chapter_count=book.chapter_count,
            word_count=book.word_count,
            synced_at=now_iso,
        )
    except DriveError as exc:
        await drive_config.set_project_dirty(session, project_id, True)
        await drive_config.set_project_error(session, project_id, str(exc))
        logger.warning(f"Google Drive 同步失败: project_id={project_id}: {exc}")
        return SyncResult(
            status="error", project_id=project_id, message=str(exc)
        )
    except LookupError as exc:
        await drive_config.set_project_dirty(session, project_id, True)
        await drive_config.set_project_error(session, project_id, str(exc))
        return SyncResult(status="error", project_id=project_id, message=str(exc))


async def _upload_book(
    client: DriveClient,
    session: AsyncSession,
    project_id: str,
    book: BookContent,
) -> dict[str, object]:
    """确保文件夹存在后创建/更新 Google Doc；返回 file_id、folder_id、webViewLink。"""
    folder_id = await drive_config.get_value(
        session, drive_config.SETTING_KEY_DRIVE_FOLDER_ID
    )
    folder_id = await client.ensure_folder(folder_id)

    file_id = await drive_config.get_project_file_id(session, project_id)
    metadata: dict[str, object] | None = None
    new_file_id: str | None = file_id

    if file_id:
        try:
            metadata = await client.update_document(file_id, book.html)
        except DriveApiError:
            # 原文件不可更新（可能被删/被移走），降级为重建。
            metadata = await client.create_document(folder_id, book.name, book.html)
            new_file_id = metadata.get("id")
    else:
        found = await client.find_document(folder_id, book.name)
        if found:
            try:
                metadata = await client.update_document(found, book.html)
            except DriveApiError:
                metadata = await client.create_document(folder_id, book.name, book.html)
                new_file_id = metadata.get("id")
            else:
                new_file_id = found
        else:
            metadata = await client.create_document(folder_id, book.name, book.html)
            new_file_id = metadata.get("id")

    if not isinstance(new_file_id, str):
        raise DriveApiError("上传后未返回文件 ID")
    web_view_link = metadata.get("webViewLink")
    return {
        "file_id": new_file_id,
        "folder_id": folder_id,
        "web_view_link": web_view_link if isinstance(web_view_link, str) else None,
    }


async def run_periodic_sync_check() -> None:
    """定时兜底：处理变脏项目，或按间隔比较内容哈希。"""
    from app.storage.database import create_session

    session = await create_session()
    try:
        if not await drive_config.is_connected(session):
            return
        project_ids = await drive_config.list_sync_enabled_project_ids(session)
        if not project_ids:
            return
        interval_minutes = await drive_config.get_int(
            session,
            drive_config.SETTING_KEY_SYNC_INTERVAL_MINUTES,
            drive_config.DEFAULT_SYNC_INTERVAL_MINUTES,
        )
        for project_id in project_ids:
            dirty = await drive_config.is_project_dirty(session, project_id)
            last_attempt = await drive_config.get_value(
                session, drive_config.SETTING_KEY_LAST_SYNC_ATTEMPT
            )
            gap_seconds = _age_seconds(last_attempt)
            if dirty and gap_seconds >= drive_config.AUTO_SYNC_MIN_GAP_SECONDS:
                result = await sync_project(session, project_id, manual=False)
                _log_result(project_id, result, "change")
                continue
            if gap_seconds >= interval_minutes * 60:
                try:
                    book = await build_book_content(session, project_id)
                except (LookupError, DriveNoContentError):
                    continue
                stored_hash = await drive_config.get_project_hash(session, project_id)
                if stored_hash != book.content_hash:
                    result = await sync_project(session, project_id, manual=False)
                    _log_result(project_id, result, "fallback")
        await session.commit()
    except Exception as exc:
        logger.warning(f"Google Drive 定时检查失败: {exc}")
    finally:
        await session.close()


def _log_result(project_id: str, result: SyncResult, trigger: str) -> None:
    if result.status == "synced":
        logger.info(
            f"Google Drive 自动同步（{trigger}）: project_id={project_id} "
            f"file_id={result.file_id}"
        )
    elif result.status == "error":
        logger.warning(
            f"Google Drive 自动同步失败（{trigger}）: project_id={project_id}: "
            f"{result.message}"
        )


def _age_seconds(value: str | None) -> float:
    if not value:
        return float("inf")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return float("inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (datetime.now(UTC) - parsed).total_seconds()
