# -*- coding: utf-8 -*-
"""Project chapter retrieval index API tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.background.jobs.models import BackgroundJob, BackgroundJobItem
from app.background.jobs.states import JOB_STATUS_CANCELLED
from app.background.runtime.supervisor import get_background_supervisor
from app.models.repos import model_provider_repo, model_repo
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.repos import retrieval_chapter_index_state_repo, setting_repo


async def _create_project(client: AsyncClient) -> tuple[str, str]:
    response = await client.post("/api/v1/projects", data={"title": "Uji Retrieval"})
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
    content: str = "Isi utama",
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
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")

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
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")
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
    chapter = await _create_chapter(client, project_id, volume_id, title="Bab Satu", content="Isi utama")
    await setting_repo.upsert(session, "index_mode", "all")
    session.add(
        RetrievalChapterIndexState(
            project_id=project_id,
            chapter_id=chapter["id"],
            index_key=f"chapters:{project_id}",
            status="ready",
            source_hash=compute_chapter_source_hash("Isi utama"),
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
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 400
    assert "belum mengaktifkan indeks" in response.json()["detail"]


@pytest.mark.asyncio
async def test_index_start_requires_embedding_model(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")
    # Indeks diaktifkan tetapi model embedding belum dikonfigurasi
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 400
    assert "model embedding" in response.json()["detail"]


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
    first = await _create_chapter(client, project_id, volume_id, title="Satu")
    await _create_chapter(client, project_id, volume_id, title="Dua")
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
    # first ditandai ready tetapi hash isinya tidak cocok -> dianggap kedaluwarsa; second belum terindeks -> total 2 masuk antrean
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
async def test_index_start_batches_item_and_state_enqueue(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.retrieval.chapter_index as chapter_index
    from app.background.jobs import service as background_service

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    for index in range(3):
        await _create_chapter(client, project_id, volume_id, title=f"Bab {index + 1}")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    async def unexpected_individual_enqueue(*_args, **_kwargs):
        raise AssertionError("index enqueue must not create items or states individually")

    monkeypatch.setattr(background_service, "create_item", unexpected_individual_enqueue)
    monkeypatch.setattr(
        chapter_index.ChapterIndexIntegrationService,
        "mark_chapter_queued",
        unexpected_individual_enqueue,
    )

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")

    assert response.status_code == 200
    assert response.json()["enqueued_count"] == 3


@pytest.mark.asyncio
async def test_index_stop_cancels_pending_job_and_resets_incomplete_chapters(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    from sqlalchemy import select
    from sqlmodel import col

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, title="Bab Satu")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    start_response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/start")
    assert start_response.status_code == 200

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/stop")

    assert response.status_code == 200
    assert response.json() == {"project_id": project_id, "stopped_count": 1}
    job = (
        await session.execute(
            select(BackgroundJob).where(
                col(BackgroundJob.subject_id) == project_id
            )
        )
    ).scalar_one()
    item = (
        await session.execute(
            select(BackgroundJobItem).where(
                col(BackgroundJobItem.job_id) == job.id
            )
        )
    ).scalar_one()
    chapter_state = await retrieval_chapter_index_state_repo.get_by_project_and_chapter(
        session,
        project_id=project_id,
        chapter_id=chapter["id"],
        index_key=f"chapters:{project_id}",
    )

    assert job.status == JOB_STATUS_CANCELLED
    assert item.status == JOB_STATUS_CANCELLED
    assert chapter_state is not None
    assert chapter_state.status == "needs_rebuild"
    assert chapter_state.job_id is None
    assert chapter_state.item_id is None
    assert chapter_state.error_message is None


@pytest.mark.asyncio
async def test_index_stop_interrupts_running_index_job(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id, _ = await _create_project(client)
    job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        subject_type="project",
        subject_id=project_id,
        status="running",
        payload_json='{"project_id":"test"}',
    )
    session.add(job)
    await session.commit()

    interrupted_job_ids: list[str] = []
    monkeypatch.setattr(
        get_background_supervisor(),
        "cancel_running_index_batch",
        interrupted_job_ids.append,
    )

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/stop")

    assert response.status_code == 200
    assert response.json() == {"project_id": project_id, "stopped_count": 1}
    assert interrupted_job_ids == [job.id]


@pytest.mark.asyncio
async def test_background_cancel_interrupts_running_index_job(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        status="running",
        payload_json='{"project_id":"test"}',
    )
    session.add(job)
    await session.commit()

    interrupted_job_ids: list[str] = []
    monkeypatch.setattr(
        get_background_supervisor(),
        "cancel_running_index_batch",
        interrupted_job_ids.append,
    )

    response = await client.post(f"/api/v1/background/jobs/{job.id}/cancel", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "cancel_requested"
    assert interrupted_job_ids == [job.id]


@pytest.mark.asyncio
async def test_index_stop_is_idempotent_without_an_active_job(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_embedding_model(session)
    project_id, _ = await _create_project(client)

    response = await client.post(f"/api/v1/projects/{project_id}/retrieval/index/stop")

    assert response.status_code == 200
    assert response.json() == {"project_id": project_id, "stopped_count": 0}


@pytest.mark.asyncio
async def test_overall_index_status_aggregates_enabled_projects(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")
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
    """Setelah indeks dimulai manual, after_commit harus memicu pengiriman index:status (per room proyek)."""
    import asyncio

    import app.retrieval.index_status as index_status_mod
    import app.socket as socket_mod

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    monkeypatch.setattr(socket_mod, "is_connected", lambda: True)

    expected_payload = {
        "project_id": project_id,
        "enabled": True,
        "status": "indexing",
        "title": "Uji Retrieval",
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
    """Event status harus mengirim snapshot saat commit dan tidak boleh ditimpa menjadi status akhir oleh batch berikutnya."""
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
    """Respons status indeks tingkat proyek harus memuat judul proyek, bukan mengandalkan pencarian tambahan di frontend."""
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Bab Satu")
    await setting_repo.upsert(session, "index_mode", "all")
    await session.commit()

    response = await client.get(f"/api/v1/projects/{project_id}/retrieval/index/status")

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["title"] == "Uji Retrieval"


@pytest.mark.asyncio
async def test_empty_content_chapter_not_counted_as_pending(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Bab dengan isi kosong tidak boleh dihitung sebagai pending; progress hanya dihitung dari bab yang dapat diindeks."""
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Ada Isi", content="Isi utama")
    await _create_chapter(client, project_id, volume_id, title="Bab Kosong", content="")
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
    """Saat indeks dimulai, bab dengan isi kosong tidak boleh masuk antrean."""
    from sqlalchemy import select
    from sqlmodel import col

    from app.background.jobs.models import BackgroundJob, BackgroundJobItem

    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Ada Isi", content="Isi utama")
    await _create_chapter(client, project_id, volume_id, title="Bab Kosong", content="")
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
    """Saat hanya ada bab berisi kosong, status proyek harus fresh dan bukan no_index."""
    await _create_embedding_model(session)
    project_id, volume_id = await _create_project(client)
    await _create_chapter(client, project_id, volume_id, title="Bab Kosong", content="")
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
