# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient


async def _create_skill(client: AsyncClient, name: str = "Skill Uji") -> str:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": name,
            "summary": "Ringkasan singkat",
            "content": "Isi skill",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_reference_docs(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)

    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Referensi Satu", "content": "Isi satu"},
    )
    assert create_response.status_code == 201
    doc = create_response.json()
    assert doc["title"] == "Dokumen Referensi Satu"
    assert doc["content"] == "Isi satu"
    assert doc["tokens"] > 0

    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Referensi Dua", "content": ""},
    )

    list_response = await client.get(f"/api/v1/skills/{skill_db_id}/reference-docs")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 2
    assert items[0]["title"] == "Dokumen Referensi Satu"


@pytest.mark.asyncio
async def test_builtin_skill_reference_docs_are_loaded_from_yaml(client: AsyncClient) -> None:
    skills_response = await client.get("/api/v1/skills")
    assert skills_response.status_code == 200
    builtin_skills = [
        item for item in skills_response.json()["items"] if item["source"] == "builtin"
    ]
    assert builtin_skills

    reference_docs = []
    for skill in builtin_skills:
        list_response = await client.get(f"/api/v1/skills/{skill['id']}/reference-docs")
        assert list_response.status_code == 200
        if list_response.json():
            reference_docs = list_response.json()
            skill_id = skill["id"]
            break

    assert reference_docs
    assert all(doc["title"] and doc["content"] for doc in reference_docs)

    create_response = await client.post(
        f"/api/v1/skills/{skill_id}/reference-docs",
        json={"title": "Tidak Boleh Ditambah", "content": ""},
    )
    assert create_response.status_code == 400


@pytest.mark.asyncio
async def test_update_reference_doc(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Judul Asli", "content": "Isi asli"},
    )
    doc_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_id}",
        json={"title": "Judul Baru", "content": "Isi baru"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "Judul Baru"
    assert data["content"] == "Isi baru"
    assert data["tokens"] > 0


@pytest.mark.asyncio
async def test_delete_reference_doc(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Akan Dihapus", "content": ""},
    )
    doc_id = create_response.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_id}"
    )
    assert delete_response.status_code == 204

    list_response = await client.get(f"/api/v1/skills/{skill_db_id}/reference-docs")
    assert list_response.json() == []


@pytest.mark.asyncio
async def test_reference_doc_not_found_for_other_skill(client: AsyncClient) -> None:
    skill_a = await _create_skill(client, "Skill A")
    skill_b = await _create_skill(client, "Skill B")

    create_response = await client.post(
        f"/api/v1/skills/{skill_a}/reference-docs",
        json={"title": "Milik A", "content": ""},
    )
    doc_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_b}/reference-docs/{doc_id}",
        json={"title": "Dimanipulasi"},
    )
    assert update_response.status_code == 404

    delete_response = await client.delete(
        f"/api/v1/skills/{skill_b}/reference-docs/{doc_id}"
    )
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_reference_doc_skill_not_found(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/skills/nonexistent-skill/reference-docs",
        json={"title": "Judul", "content": ""},
    )
    assert create_response.status_code == 404

    list_response = await client.get("/api/v1/skills/nonexistent-skill/reference-docs")
    assert list_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_skill_cascades_reference_docs(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Referensi", "content": "Isi"},
    )

    delete_skill_response = await client.delete(f"/api/v1/skills/{skill_db_id}")
    assert delete_skill_response.status_code == 204

    list_response = await client.get(f"/api/v1/skills/{skill_db_id}/reference-docs")
    assert list_response.status_code == 404


@pytest.mark.asyncio
async def test_create_reference_doc_dedupes_duplicate_title(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)

    first = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Referensi Baru", "content": ""},
    )
    assert first.status_code == 201
    assert first.json()["title"] == "Dokumen Referensi Baru"

    second = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Referensi Baru", "content": ""},
    )
    assert second.status_code == 201
    assert second.json()["title"] == "Dokumen Referensi Baru (2)"

    third = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Referensi Baru", "content": ""},
    )
    assert third.status_code == 201
    assert third.json()["title"] == "Dokumen Referensi Baru (3)"


@pytest.mark.asyncio
async def test_create_reference_doc_keeps_unique_title(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen A", "content": ""},
    )

    response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen B", "content": ""},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Dokumen B"


@pytest.mark.asyncio
async def test_update_reference_doc_title_conflict(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Satu", "content": ""},
    )
    create_b = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen Dua", "content": ""},
    )
    doc_b_id = create_b.json()["id"]

    conflict_response = await client.patch(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_b_id}",
        json={"title": "Dokumen Satu"},
    )
    assert conflict_response.status_code == 409


@pytest.mark.asyncio
async def test_update_reference_doc_keeps_same_title(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "Dokumen", "content": ""},
    )
    doc_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_id}",
        json={"title": "Dokumen", "content": "Isi baru"},
    )
    assert update_response.status_code == 200
