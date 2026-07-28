# -*- coding: utf-8 -*-
"""章节导出 API 测试。"""

import pytest
from httpx import AsyncClient
from urllib.parse import unquote

from app.background.events.publisher import BackgroundEventPublisher
from app.background.jobs import service as background_service
from app.background.runtime.context import JobContext
from app.background.runtime.dispatcher import dispatch_job
from app.chapter_export import service as chapter_export_service
from app.background.jobs.models import BackgroundJob
from app.api.routers import chapter_exports as chapter_exports_router
from app.storage.repos import chapter_repo


def test_chinese_volume_numbers() -> None:
    assert chapter_export_service.chinese_number(1) == "一"
    assert chapter_export_service.chinese_number(10) == "十"
    assert chapter_export_service.chinese_number(11) == "十一"
    assert chapter_export_service.chinese_number(21) == "二十一"
    assert chapter_export_service.chinese_number(101) == "一百零一"


def test_expired_export_is_not_downloadable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(chapter_export_service.settings, "chapter_exports_dir", tmp_path)
    job = BackgroundJob(
        id="expired-export",
        type=chapter_export_service.EXPORT_JOB_TYPE,
        status="succeeded",
        payload_json='{"filename":"测试.txt"}',
        result_json='{"expires_at":"2020-01-01T00:00:00+00:00"}',
    )
    _part_path, output_path = chapter_export_service.export_file_paths(job.id)
    output_path.write_text("expired", encoding="utf-8")

    assert not chapter_export_service.is_export_download_available(job)


async def _create_project(client: AsyncClient, title: str = "测试小说") -> tuple[str, str]:
    response = await client.post("/api/v1/projects", data={"title": title})
    assert response.status_code == 201
    project_id = response.json()["id"]
    volumes = (await client.get(f"/api/v1/projects/{project_id}/volumes")).json()
    return project_id, volumes[0]["id"]


async def _create_chapter(
    client: AsyncClient,
    project_id: str,
    volume_id: str,
    title: str,
    content: str,
    word_count: int,
) -> dict:
    response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={
            "volume_id": volume_id,
            "title": title,
            "content": content,
            "word_count": word_count,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_create_full_volume_export_uses_volume_filename_and_snapshot_selection(
    client: AsyncClient,
) -> None:
    project_id, volume_id = await _create_project(client)
    first = await _create_chapter(client, project_id, volume_id, "第一章", "第一章正文\r\n第二行", 5)
    second = await _create_chapter(client, project_id, volume_id, "第二章", "第二章正文", 5)

    response = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [volume_id],
            "included_chapter_ids": [],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["chapter_count"] == 2
    assert data["word_count"] == 10
    assert data["filename"] == "测试小说-全本-2026-07-28.txt"
    assert data["chapter_ids"] == [first["id"], second["id"]]


@pytest.mark.asyncio
async def test_export_creation_does_not_load_chapter_bodies(client: AsyncClient, monkeypatch) -> None:
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, "第一章", "正文", 2)

    async def reject_full_chapter_load(*_args, **_kwargs):
        raise AssertionError("导出创建阶段不应读取完整章节正文")

    monkeypatch.setattr(chapter_repo, "list_by_project", reject_full_chapter_load)
    response = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [],
            "included_chapter_ids": [chapter["id"]],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_only_cancel_endpoint_preempts_running_export(client: AsyncClient, monkeypatch) -> None:
    class Supervisor:
        def __init__(self) -> None:
            self.cancelled_job_ids: list[str] = []

        def create_event_publisher(self) -> BackgroundEventPublisher:
            return BackgroundEventPublisher(None)

        def cancel_running_chapter_export(self, job_id: str) -> bool:
            self.cancelled_job_ids.append(job_id)
            return False

    supervisor = Supervisor()
    monkeypatch.setattr(chapter_exports_router, "get_background_supervisor", lambda: supervisor)
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, "第一章", "正文", 2)

    created = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [],
            "included_chapter_ids": [chapter["id"]],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )
    assert created.status_code == 201
    assert supervisor.cancelled_job_ids == []

    cancelled = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports/{created.json()['id']}/cancel"
    )
    assert cancelled.status_code == 200
    assert supervisor.cancelled_job_ids == [created.json()["id"]]


@pytest.mark.asyncio
async def test_create_fragment_export_uses_chapter_filename(client: AsyncClient) -> None:
    project_id, volume_id = await _create_project(client)
    selected = await _create_chapter(client, project_id, volume_id, "第一章", "正文", 2)
    await _create_chapter(client, project_id, volume_id, "第二章", "正文", 2)

    response = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [],
            "included_chapter_ids": [selected["id"]],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "测试小说-1个章节-2026-07-28.txt"


@pytest.mark.asyncio
async def test_manually_selected_complete_volume_still_uses_chapter_format(
    client: AsyncClient,
) -> None:
    project_id, volume_id = await _create_project(client)
    first = await _create_chapter(client, project_id, volume_id, "第一章", "正文", 2)
    second = await _create_chapter(client, project_id, volume_id, "第二章", "正文", 2)

    response = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [],
            "included_chapter_ids": [first["id"], second["id"]],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "测试小说-2个章节-2026-07-28.txt"


@pytest.mark.asyncio
async def test_create_export_rejects_empty_selection(client: AsyncClient) -> None:
    project_id, _volume_id = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [],
            "included_chapter_ids": [],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )

    assert response.status_code == 400
    assert "章节" in response.json()["detail"]


@pytest.mark.asyncio
async def test_export_task_writes_full_volume_txt_and_serves_download(
    client: AsyncClient,
    session,
    monkeypatch,
    tmp_path,
) -> None:
    async def skip_cancellation_check(_context: JobContext) -> None:
        return None

    monkeypatch.setattr(chapter_export_service.settings, "chapter_exports_dir", tmp_path)
    monkeypatch.setattr(JobContext, "check_cancelled", skip_cancellation_check)
    project_id, volume_id = await _create_project(client)
    first = await _create_chapter(client, project_id, volume_id, "第一章", "第一章正文\r\n第二行", 5)
    second = await _create_chapter(client, project_id, volume_id, "第二章", "第二章正文", 5)
    created = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [volume_id],
            "included_chapter_ids": [],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )
    assert created.status_code == 201
    job = await background_service.get_job(session, created.json()["id"])
    assert job is not None
    job.status = "running"
    await session.commit()

    context = JobContext(session=session, job=job, publisher=BackgroundEventPublisher(None))
    result = await dispatch_job(context)
    await background_service.mark_succeeded(session, context.publisher, context.job, result=result)
    await session.commit()

    status_response = await client.get(
        f"/api/v1/projects/{project_id}/chapter-exports/{job.id}"
    )
    assert status_response.status_code == 200
    assert status_response.json()["current"] == 2
    assert status_response.json()["total"] == 2
    assert status_response.json()["download_url"]

    download_response = await client.get(
        f"/api/v1/projects/{project_id}/chapter-exports/{job.id}/download"
    )
    assert download_response.status_code == 200
    assert "attachment" in download_response.headers["content-disposition"]
    assert "测试小说-全本-2026-07-28.txt" in unquote(
        download_response.headers["content-disposition"]
    )
    assert download_response.content.decode("utf-8-sig") == (
        "第一卷 第一卷\n"
        "第一章\n第一章正文\n第二行\n\n第二章\n第二章正文"
    )
    assert result == {
        "filename": "测试小说-全本-2026-07-28.txt",
        "volume_count": 1,
        "chapter_count": 2,
        "word_count": 10,
        "expires_at": result["expires_at"],
    }
    assert [first["id"], second["id"]] == created.json()["chapter_ids"]


@pytest.mark.asyncio
async def test_cancelled_export_removes_partial_file(
    client: AsyncClient,
    session,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(chapter_export_service.settings, "chapter_exports_dir", tmp_path)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, "第一章", "正文", 2)
    created = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports",
        json={
            "selected_volume_ids": [volume_id],
            "included_chapter_ids": [],
            "excluded_chapter_ids": [],
            "local_date": "2026-07-28",
        },
    )
    job_id = created.json()["id"]
    part_path, output_path = chapter_export_service.export_file_paths(job_id)
    part_path.write_text("partial", encoding="utf-8")
    output_path.write_text("complete", encoding="utf-8")

    cancelled = await client.post(
        f"/api/v1/projects/{project_id}/chapter-exports/{job_id}/cancel"
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert not part_path.exists()
    assert not output_path.exists()


@pytest.mark.asyncio
async def test_cleanup_keeps_output_while_export_is_still_running(
    session,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(chapter_export_service.settings, "chapter_exports_dir", tmp_path)
    job = BackgroundJob(
        id="running-export",
        type=chapter_export_service.EXPORT_JOB_TYPE,
        status="running",
        payload_json="{}",
    )
    session.add(job)
    await session.commit()
    _part_path, output_path = chapter_export_service.export_file_paths(job.id)
    output_path.write_text("finished but not committed", encoding="utf-8")

    assert await chapter_export_service.cleanup_chapter_export_files(session) == 0
    assert output_path.exists()
