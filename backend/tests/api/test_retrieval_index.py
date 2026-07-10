# -*- coding: utf-8 -*-
"""Project chapter retrieval index API tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.models.repos import model_provider_repo, model_repo
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.repos import setting_repo


async def _create_project(client: AsyncClient) -> tuple[str, str]:
    response = await client.post("/api/v1/projects", data={"title": "检索测试"})
    assert response.status_code == 201
    project_id = response.json()["id"]
    volumes = (await client.get(f"/api/v1/projects/{project_id}/volumes")).json()
    return project_id, volumes[0]["id"]


async def _create_chapter(
    client: AsyncClient,
    project_id: str,
    volume_id: str,
    *,
    title: str,
    content: str = "正文",
) -> dict:
    response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": title, "content": content},
    )
    assert response.status_code == 201
    return response.json()


async def _create_embedding_model(session: AsyncSession):
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    provider = await model_provider_repo.create(
        session=session,
        name="Embedding Provider",
        url="https://api.test.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        provider_type="openai",
    )
    model = await model_repo.create(
        session=session,
        name="Embedding Model",
        provider_id=provider.id,
        model_id="text-embedding-test",
        task_type="embedding",
        dimensions=3,
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    return model


@pytest.mark.asyncio
async def test_index_status_disabled_by_default(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["enabled"] is False
    assert data["status"] == "disabled"
    assert data["total_chapters"] == 1


@pytest.mark.asyncio
async def test_index_status_reports_no_index_when_enabled_but_unindexed(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    data = response.json()
    assert data["enabled"] is True
    assert data["status"] == "no_index"
    assert data["total_chapters"] == 1
    assert data["pending_count"] == 1
    assert data["indexed_count"] == 0


@pytest.mark.asyncio
async def test_index_status_reports_fresh_when_all_chapters_ready(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    from app.retrieval.chapter_index import compute_chapter_source_hash

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, title="一章", content="正文")
    await setting_repo.upsert(session, "index_mode", "all")
    session.add(
        RetrievalChapterIndexState(
            project_id=project_id,
            chapter_id=chapter["id"],
            index_key=f"chapters:{project_id}",
            status="ready",
            source_hash=compute_chapter_source_hash("正文"),
            embedding_model_ref_id="model-1",
            chunk_count=1,
        )
    )
    await session.commit()

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    data = response.json()
    assert data["status"] == "fresh"
    assert data["indexed_count"] == 1
    assert data["pending_count"] == 0
    assert data["progress"] == 1.0


@pytest.mark.asyncio
async def test_index_start_requires_enabled_project(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 400
    assert "未启用" in response.json()["detail"]


@pytest.mark.asyncio
async def test_index_start_requires_embedding_model(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")
    # 启用索引但未配置嵌入模型
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 400
    assert "嵌入模型" in response.json()["detail"]


@pytest.mark.asyncio
async def test_index_start_enqueues_outdated_chapters(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    from sqlalchemy import select
    from sqlmodel import col

    from app.background.jobs.models import BackgroundJob, BackgroundJobItem

    model = await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    first = await _create_chapter(client, project_id, volume_id, title="一")
    await _create_chapter(client, project_id, volume_id, title="二")
    await setting_repo.upsert(session, "index_mode", "all")
    session.add(
        RetrievalChapterIndexState(
            project_id=project_id,
            chapter_id=first["id"],
            index_key=f"chapters:{project_id}",
            status="ready",
            source_hash="old",
            embedding_model_ref_id=model.id,
            chunk_count=2,
        )
    )
    await session.commit()

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    # first 标记为 ready 但内容哈希不匹配 -> 视为过期；second 未索引 -> 共 2 个入队
    assert data["enqueued_count"] == 2
    assert "job_id" not in data
    jobs = (
        await session.execute(
            select(BackgroundJob).where(col(BackgroundJob.subject_id) == project_id)
        )
    ).scalars().all()
    assert len(jobs) == 1
    items = (
        await session.execute(
            select(BackgroundJobItem).where(
                col(BackgroundJobItem.job_id) == jobs[0].id
            )
        )
    ).scalars().all()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_overall_index_status_aggregates_enabled_projects(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.get("/api/v1/retrieval/index/status")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "all"
    assert data["embedding_model_configured"] is True
    assert data["total_projects"] == 1
    assert data["total_chapters"] == 1
    assert data["pending_count"] == 1
    assert data["projects"][0]["project_id"] == project_id
    assert data["projects"][0]["status"] == "no_index"


@pytest.mark.asyncio
async def test_index_start_emits_status_event_after_commit(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch,
) -> None:
    """手动开始索引后，after_commit 应触发 index:status 推送（按项目房间）。"""
    import asyncio

    import app.retrieval.index_status as index_status_mod
    import app.socket as socket_mod

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    monkeypatch.setattr(socket_mod, "is_connected", lambda: True)

    expected_payload = {
        "project_id": project_id,
        "enabled": True,
        "status": "indexing",
        "title": "检索测试",
        "total_chapters": 1,
        "indexed_count": 0,
        "pending_count": 1,
        "in_progress_count": 0,
        "failed_count": 0,
        "progress": 0.0,
    }

    async def fake_payload(*_args, **_kwargs):
        return expected_payload

    monkeypatch.setattr(index_status_mod, "emit_project_index_status_payload", fake_payload)

    captured: dict[str, object] = {}
    done = asyncio.Event()

    async def fake_emit(event, data, *, room=None):  # noqa: ANN001
        captured["event"] = event
        captured["data"] = data
        captured["room"] = room
        done.set()

    monkeypatch.setattr(index_status_mod, "emit", fake_emit)

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")
    assert response.status_code == 200

    await asyncio.wait_for(done.wait(), timeout=2.0)

    assert captured["event"] == "index:status"
    assert captured["room"] == f"background:project:{project_id}"
    assert captured["data"] == expected_payload


@pytest.mark.asyncio
async def test_commit_and_emit_index_status_keeps_committed_progress_snapshot(
    session: AsyncSession,
    monkeypatch,
) -> None:
    """状态事件必须发送提交时的快照，不能被后续批次覆盖为最终状态。"""
    import app.retrieval.index_status as index_status_mod

    payloads = [
        {"project_id": "project-1", "indexed_count": 10},
        {"project_id": "project-1", "indexed_count": 20},
    ]
    emitted: list[dict[str, object]] = []

    async def fake_payload(*_args, **_kwargs):
        return payloads.pop(0)

    async def fake_emit(_event, data, **_kwargs):
        emitted.append(data)

    monkeypatch.setattr(index_status_mod, "emit_project_index_status_payload", fake_payload)
    monkeypatch.setattr(index_status_mod, "emit", fake_emit)
    monkeypatch.setattr("app.socket.is_connected", lambda: True)

    await index_status_mod.commit_and_emit_index_status(session, "project-1")
    await index_status_mod.commit_and_emit_index_status(session, "project-1")

    assert emitted == [
        {"project_id": "project-1", "indexed_count": 10},
        {"project_id": "project-1", "indexed_count": 20},
    ]


@pytest.mark.asyncio
async def test_index_status_payload_includes_title(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """项目级索引状态响应应包含项目标题而非依赖前端另行查找。"""
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="一章")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["title"] == "检索测试"


@pytest.mark.asyncio
async def test_empty_content_chapter_not_counted_as_pending(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """空内容的章节不应计入 pending，progress 只按可索引章节计算。"""
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="有内容", content="正文")
    await _create_chapter(client, project_id, volume_id, title="空章节", content="")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    data = response.json()
    assert data["enabled"] is True
    assert data["total_chapters"] == 2
    assert data["empty_content_count"] == 1
    assert data["pending_count"] == 1
    assert data["indexed_count"] == 0
    assert data["progress"] == 0.0


@pytest.mark.asyncio
async def test_empty_content_chapter_not_enqueued_for_indexing(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """启动索引时，空内容章节不应入队。"""
    from sqlalchemy import select
    from sqlmodel import col

    from app.background.jobs.models import BackgroundJob, BackgroundJobItem

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="有内容", content="正文")
    await _create_chapter(client, project_id, volume_id, title="空章节", content="")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 200
    data = response.json()
    assert data["enqueued_count"] == 1
    assert data["skipped_count"] == 1
    jobs = (
        await session.execute(
            select(BackgroundJob).where(col(BackgroundJob.subject_id) == project_id)
        )
    ).scalars().all()
    assert len(jobs) == 1
    items = (
        await session.execute(
            select(BackgroundJobItem).where(col(BackgroundJobItem.job_id) == jobs[0].id)
        )
    ).scalars().all()
    assert len(items) == 1


@pytest.mark.asyncio
async def test_empty_content_only_chapter_project_status_fresh(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """只有空内容章节时，项目状态应为 fresh 而非 no_index。"""
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="空章节", content="")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    data = response.json()
    assert data["total_chapters"] == 1
    assert data["empty_content_count"] == 1
    assert data["pending_count"] == 0
    assert data["indexed_count"] == 0
    assert data["status"] == "fresh"
    assert data["progress"] == 0.0
