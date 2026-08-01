# -*- coding: utf-8 -*-
"""Google Drive 同步服务单元测试。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.google_drive import config as drive_config
from app.google_drive.errors import DriveNotConnectedError
from app.google_drive.service import (
    DriveNoContentError,
    build_book_content,
    schedule_project_sync,
    sync_project,
)
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo, project_repo, volume_repo


async def _seed_project(session: AsyncSession) -> str:
    project = await project_repo.create(session, Project(title="测试小说"))
    await volume_repo.create(
        session, Volume(project_id=project.id, title="第一卷", order=1)
    )
    await session.commit()
    return project.id


async def _seed_chapter(
    session: AsyncSession,
    project_id: str,
    volume_id: str,
    *,
    title: str = "第一章",
    content: str = "正文内容",
    order: int = 1,
) -> str:
    chapter = await chapter_repo.create(
        session,
        Chapter(
            project_id=project_id,
            volume_id=volume_id,
            title=title,
            content=content,
            order=order,
        ),
    )
    await session.commit()
    return chapter.id


@pytest.mark.asyncio
async def test_schedule_project_sync_marks_dirty_when_enabled(session: AsyncSession) -> None:
    project_id = await _seed_project(session)
    await drive_config.set_project_sync_enabled(session, project_id, True)
    await session.commit()

    assert not await drive_config.is_project_dirty(session, project_id)
    await schedule_project_sync(session, project_id)
    await session.commit()

    assert await drive_config.is_project_dirty(session, project_id)


@pytest.mark.asyncio
async def test_schedule_project_sync_skips_disabled(session: AsyncSession) -> None:
    project_id = await _seed_project(session)

    await schedule_project_sync(session, project_id)
    await session.commit()

    assert not await drive_config.is_project_dirty(session, project_id)


@pytest.mark.asyncio
async def test_build_book_content_includes_all_chapters(session: AsyncSession) -> None:
    project_id = await _seed_project(session)
    volumes = await volume_repo.list_by_project(session, project_id)
    await _seed_chapter(session, project_id, volumes[0].id, title="第一章", content="正文一", order=1)
    await _seed_chapter(session, project_id, volumes[0].id, title="第二章", content="正文二", order=2)

    book = await build_book_content(session, project_id)

    assert book.chapter_count == 2
    assert book.name == "测试小说（自动同步）"
    assert "<h1>测试小说</h1>" in book.html
    assert "<h3>第一章</h3>" in book.html
    assert "<h3>第二章</h3>" in book.html
    assert "<p>正文一</p>" in book.html
    assert book.content_hash  # 非空


@pytest.mark.asyncio
async def test_build_book_content_raises_when_no_chapters(session: AsyncSession) -> None:
    project_id = await _seed_project(session)

    with pytest.raises(DriveNoContentError):
        await build_book_content(session, project_id)


@pytest.mark.asyncio
async def test_sync_project_raises_when_not_connected(session: AsyncSession) -> None:
    project_id = await _seed_project(session)
    volumes = await volume_repo.list_by_project(session, project_id)
    await _seed_chapter(session, project_id, volumes[0].id)

    result = await sync_project(session, project_id)

    assert result.status == "error"
    assert "尚未连接" in (result.message or "")


@pytest.mark.asyncio
async def test_sync_project_unchanged_skips_upload(session: AsyncSession, monkeypatch) -> None:
    project_id = await _seed_project(session)
    volumes = await volume_repo.list_by_project(session, project_id)
    await _seed_chapter(session, project_id, volumes[0].id)

    # 预置一个与内容匹配的 hash 且不脏，模拟已经同步过。
    book = await build_book_content(session, project_id)
    await drive_config.set_project_sync_enabled(session, project_id, True)
    await drive_config.set_project_hash(session, project_id, book.content_hash)
    await drive_config.set_value(
        session, drive_config.SETTING_KEY_LAST_SYNC_ATTEMPT, "2020-01-01T00:00:00+00:00"
    )
    # 预置假 refresh token 绕过连接检查。
    await drive_config.set_refresh_token(session, "fake-refresh")
    await session.commit()

    called = []

    async def _fake_get_access_token(sess):
        called.append("get_access_token")
        return "fake-token"

    monkeypatch.setattr(
        "app.google_drive.service.oauth.get_access_token", _fake_get_access_token
    )

    result = await sync_project(session, project_id, manual=False)

    assert result.status == "unchanged"
    assert called == []
    assert result.chapter_count == 1


@pytest.mark.asyncio
async def test_sync_project_uploads_when_dirty(session: AsyncSession, monkeypatch) -> None:
    project_id = await _seed_project(session)
    volumes = await volume_repo.list_by_project(session, project_id)
    await _seed_chapter(session, project_id, volumes[0].id)

    await drive_config.set_project_sync_enabled(session, project_id, True)
    await drive_config.set_project_dirty(session, project_id, True)
    await drive_config.set_refresh_token(session, "fake-refresh")
    await session.commit()

    class _FakeClient:
        def __init__(self, token: str) -> None:
            self.token = token

        async def ensure_folder(self, folder_id):
            return "folder-1"

        async def find_document(self, folder_id, name):
            return None

        async def create_document(self, folder_id, name, html):
            return {
                "id": "file-1",
                "name": name,
                "mimeType": "application/vnd.google-apps.document",
                "webViewLink": "https://docs.google.com/document/d/file-1/edit",
            }

        async def update_document(self, file_id, html):
            return {"id": file_id}

    async def _fake_get_access_token(sess) -> str:
        return "fake-token"

    monkeypatch.setattr("app.google_drive.service.DriveClient", _FakeClient)
    monkeypatch.setattr(
        "app.google_drive.service.oauth.get_access_token", _fake_get_access_token
    )

    result = await sync_project(session, project_id, manual=False)
    await session.commit()

    assert result.status == "synced"
    assert result.file_id == "file-1"
    assert result.chapter_count == 1
    assert await drive_config.get_project_file_id(session, project_id) == "file-1"
    assert await drive_config.get_project_hash(session, project_id) == (
        await build_book_content(session, project_id)
    ).content_hash
    assert not await drive_config.is_project_dirty(session, project_id)
    assert await drive_config.get_project_error(session, project_id) is None


@pytest.mark.asyncio
async def test_sync_project_error_sets_dirty_and_error(session: AsyncSession, monkeypatch) -> None:
    project_id = await _seed_project(session)
    volumes = await volume_repo.list_by_project(session, project_id)
    await _seed_chapter(session, project_id, volumes[0].id)

    await drive_config.set_project_sync_enabled(session, project_id, True)
    await drive_config.set_refresh_token(session, "fake-refresh")
    await session.commit()

    async def _fail_get_access_token(sess):
        raise DriveNotConnectedError("尚未连接 Google 账号")

    monkeypatch.setattr(
        "app.google_drive.service.oauth.get_access_token", _fail_get_access_token
    )

    result = await sync_project(session, project_id)
    await session.commit()

    assert result.status == "error"
    assert "尚未连接" in (result.message or "")
    assert await drive_config.is_project_dirty(session, project_id)
    assert await drive_config.get_project_error(session, project_id)
