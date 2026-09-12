# -*- coding: utf-8 -*-
"""
Uji API Project.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agent_runtime.persistence import repo as agent_run_repo
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentRunMessage,
    PlanRecord,
    PlanTodoRecord,
)
from app.storage.models.task import Task
from app.storage.models.task_message import TaskMessage
from app.storage.services import task_service


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    """Uji pembuatan proyek."""
    response = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji", "description": "Ini adalah novel uji"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Novel Uji"
    assert data["description"] == "Ini adalah novel uji"
    assert data["word_count"] == 0
    assert data["chapter_count"] == 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_project_without_description(client: AsyncClient) -> None:
    """Uji pembuatan proyek tanpa ringkasan."""
    response = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Tanpa Ringkasan"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Novel Tanpa Ringkasan"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_project_empty_title(client: AsyncClient) -> None:
    """Uji pembuatan proyek dengan judul kosong."""
    response = await client.post(
        "/api/v1/projects",
        data={"title": ""},
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient) -> None:
    """Uji pengambilan daftar proyek yang kosong."""
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    """Uji pengambilan daftar proyek."""
    # Buat beberapa proyek
    for i in range(3):
        await client.post(
            "/api/v1/projects",
            data={"title": f"Novel {i + 1}"},
        )

    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_projects_pagination(client: AsyncClient) -> None:
    """Uji paginasi daftar proyek."""
    # Buat 5 proyek
    for i in range(5):
        await client.post(
            "/api/v1/projects",
            data={"title": f"Novel {i + 1}"},
        )

    # Ambil halaman pertama
    response = await client.get("/api/v1/projects?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2

    # Ambil halaman kedua
    response = await client.get("/api/v1/projects?page=2&page_size=2")
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_list_projects_search_and_sort(client: AsyncClient) -> None:
    """Uji pencarian dan pengurutan daftar proyek di sisi server."""
    await client.post(
        "/api/v1/projects",
        data={"title": "Proyek Zeta", "description": "Memuat kata sasaran"},
    )
    await client.post(
        "/api/v1/projects",
        data={"title": "Proyek Alpha", "description": "Ringkasan biasa"},
    )
    await client.post(
        "/api/v1/projects",
        data={"title": "Proyek Beta", "description": "Kata sasaran lainnya"},
    )

    search_response = await client.get(
        "/api/v1/projects?search=kata sasaran&page=1&page_size=1",
    )
    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data["total"] == 2
    assert len(search_data["items"]) == 1

    sort_response = await client.get(
        "/api/v1/projects?sort_by=title&sort_order=asc&page_size=100",
    )
    assert sort_response.status_code == 200
    assert [item["title"] for item in sort_response.json()["items"]] == [
        "Proyek Alpha",
        "Proyek Beta",
        "Proyek Zeta",
    ]


@pytest.mark.asyncio
async def test_list_projects_supports_pinyin_search_and_sort(client: AsyncClient) -> None:
    """Pencarian pinyin dan pengurutan judul harus tetap konsisten dengan klien lama.

    Fixture CJK di uji ini sengaja dipertahankan: pencarian "hxxm" mengandalkan
    inisial pinyin judul Tionghoa dan urutannya juga mengikuti urutan pinyin.
    """
    await client.post("/api/v1/projects", data={"title": "中篇项目"})
    await client.post("/api/v1/projects", data={"title": "红星项目", "description": "银河故事"})
    await client.post("/api/v1/projects", data={"title": "阿尔法项目"})

    search_response = await client.get("/api/v1/projects?search=hxxm")
    assert search_response.status_code == 200
    assert [item["title"] for item in search_response.json()["items"]] == ["红星项目"]

    sort_response = await client.get(
        "/api/v1/projects?sort_by=title&sort_order=asc&page_size=100",
    )
    assert sort_response.status_code == 200
    assert [item["title"] for item in sort_response.json()["items"]] == [
        "阿尔法项目",
        "红星项目",
        "中篇项目",
    ]


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient) -> None:
    """Uji pengambilan detail proyek."""
    # Buat proyek
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji", "description": "Ringkasan uji"},
    )
    project_id = create_response.json()["id"]

    # Ambil proyek
    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["title"] == "Novel Uji"
    assert data["description"] == "Ringkasan uji"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """Uji pengambilan proyek yang tidak ada."""
    response = await client.get("/api/v1/projects/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    """Uji pembaruan proyek."""
    # Buat proyek
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "Judul Asli", "description": "Ringkasan asli"},
    )
    project_id = create_response.json()["id"]

    # Perbarui proyek
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        data={"title": "Judul Baru", "description": "Ringkasan baru"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Judul Baru"
    assert data["description"] == "Ringkasan baru"


@pytest.mark.asyncio
async def test_update_project_partial(client: AsyncClient) -> None:
    """Uji pembaruan sebagian proyek."""
    # Buat proyek
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "Judul Asli", "description": "Ringkasan asli"},
    )
    project_id = create_response.json()["id"]

    # Perbarui hanya judul
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        data={"title": "Judul Baru"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Judul Baru"
    assert data["description"] == "Ringkasan asli"  # Ringkasan tidak berubah


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient) -> None:
    """Uji pembaruan proyek yang tidak ada."""
    response = await client.patch(
        "/api/v1/projects/nonexistent",
        data={"title": "Judul Baru"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """Uji penghapusan proyek."""
    # Buat proyek
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Akan Dihapus"},
    )
    project_id = create_response.json()["id"]

    # Hapus proyek
    response = await client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204

    # Pastikan sudah terhapus
    get_response = await client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_deletes_tasks_and_runtime_data(client, session) -> None:
    create_response = await client.post("/api/v1/projects", data={"title": "Proyek Akan Dihapus"})
    project_id = create_response.json()["id"]
    task = await task_service.create_task(
        session,
        project_id=project_id,
        title="Tugas Akan Dihapus",
        mode="agent",
        agent_session_id="project-delete-session",
    )
    await create_child_run(
        session,
        parent_session_id="project-delete-session",
        parent_task_id=task.id,
        parent_thread_id="project-delete-session",
        child_thread_id="project-delete-session:child:writer",
        agent_key="writer",
        dispatch_id="writer",
        tool_call_id="tool-writer",
        request={"task": "write", "input": {}, "metadata": {}},
    )
    await agent_run_repo.insert_message(
        session,
        session_id="project-delete-session",
        task_id=task.id,
        project_id=project_id,
        role="assistant",
        content="runtime message",
        status="completed",
    )
    session.add(
        TaskMessage(
            id="project-delete-message",
            task_id=task.id,
            role="assistant",
            content="legacy runtime message",
            tool_calls="[]",
            message_metadata="{}",
        )
    )
    session.add_all(
        [
            AgentContextCompaction(
                session_id="project-delete-session",
                task_id=task.id,
                project_id=project_id,
                start_seq=0,
                end_seq=1,
                summary="runtime summary",
                trigger="manual",
            ),
            PlanRecord(id="project-delete-plan", session_id="project-delete-session"),
            PlanTodoRecord(
                id="project-delete-todo",
                plan_id="project-delete-plan",
                content="runtime todo",
                sort_index=0,
            ),
        ]
    )
    await session.commit()

    with patch(
        "app.api.routers.projects.delete_checkpoints_for_thread",
        new=AsyncMock(return_value=0),
    ) as delete_checkpoints:
        response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 204
    assert delete_checkpoints.await_count == 2
    for model in (
        Task,
        TaskMessage,
        AgentRunMessage,
        AgentChildRun,
        AgentChildRunRequest,
        AgentContextCompaction,
        PlanRecord,
        PlanTodoRecord,
    ):
        result = await session.execute(select(model))
        assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_project_rejects_running_tasks(client, session) -> None:
    create_response = await client.post("/api/v1/projects", data={"title": "Proyek Berjalan"})
    project_id = create_response.json()["id"]
    task = await task_service.create_task(
        session,
        project_id=project_id,
        title="Tugas Berjalan",
        mode="agent",
        agent_session_id="running-project-session",
    )
    task.is_running = True
    await session.commit()

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Proyek memiliki tugas yang sedang berjalan, tidak dapat dihapus"
    )


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    """Uji penghapusan proyek yang tidak ada."""
    response = await client.delete("/api/v1/projects/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_cleans_retrieval_state(client, session, tmp_path) -> None:
    """Hapus proyek wajib membuang state retrieval, bukan meninggalkan yatim.

    Sebelum perbaikan ini, baris ``retrieval_chapter_index_states`` dan
    ``retrieval_indexes`` tetap tertinggal setiap kali proyek dihapus. Pembuangan
    berkas indeks di disk diuji terpisah pada ``test_service_drop_index.py``.
    """
    from app.retrieval.chapter_index import chapter_index_key
    from app.retrieval.engine_protocol import (
        KEYWORD_ONLY_DIMENSIONS,
        KEYWORD_ONLY_EMBEDDING_REF_ID,
    )
    from app.retrieval.service import OpenFicRetrievalService
    from app.retrieval.types import (
        FilterableField,
        FilterableFieldType,
        RetrievalIndexContract,
    )
    from app.storage.models.retrieval_chapter_index_state import (
        RetrievalChapterIndexState,
    )
    from app.storage.models.retrieval_index import RetrievalIndex

    create_response = await client.post(
        "/api/v1/projects", data={"title": "Proyek Berindeks"}
    )
    project_id = create_response.json()["id"]
    volume_id = (
        await client.get(f"/api/v1/projects/{project_id}/volumes")
    ).json()[0]["id"]
    chapter_id = (
        await client.post(
            f"/api/v1/projects/{project_id}/chapters",
            json={"volume_id": volume_id, "title": "Bab Satu", "content": "Isi bab"},
        )
    ).json()["id"]

    index_key = chapter_index_key(project_id)
    await OpenFicRetrievalService(base_dir=tmp_path).register_index(
        session,
        index_key,
        RetrievalIndexContract(
            embedding_model_ref_id=KEYWORD_ONLY_EMBEDDING_REF_ID,
            embedding_model_id_snapshot=KEYWORD_ONLY_EMBEDDING_REF_ID,
            embedding_dimensions_snapshot=KEYWORD_ONLY_DIMENSIONS,
            chunk_size=400,
            chunk_overlap=40,
            filterable_fields=[
                FilterableField(
                    name="project_id", field_type=FilterableFieldType.STRING
                ),
            ],
        ),
    )
    session.add(
        RetrievalChapterIndexState(
            project_id=project_id,
            chapter_id=chapter_id,
            index_key=index_key,
            status="ready",
            source_hash="hash-1",
            embedding_model_ref_id=KEYWORD_ONLY_EMBEDDING_REF_ID,
            chunk_count=1,
        )
    )
    await session.commit()

    with patch(
        "app.api.routers.projects.delete_checkpoints_for_thread",
        new=AsyncMock(return_value=0),
    ):
        response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 204
    for model in (RetrievalChapterIndexState, RetrievalIndex):
        result = await session.execute(select(model))
        assert result.scalars().all() == [], f"{model.__name__} meninggalkan yatim"
