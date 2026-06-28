# -*- coding: utf-8 -*-
"""
Volume API tests.
"""

import importlib
import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.ids import generate_id
from app.retrieval.chapter_index import compute_chapter_source_hash
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.models.writing_activity_event import WritingActivityEvent


async def _create_project(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _default_volume(client: AsyncClient, project_id: str) -> dict:
    response = await client.get(f"/api/v1/projects/{project_id}/volumes")
    assert response.status_code == 200
    volumes = response.json()
    assert len(volumes) == 1
    return volumes[0]


@pytest.mark.asyncio
async def test_project_creation_creates_default_volume(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    volume = await _default_volume(client, project_id)

    assert volume["id"]
    assert not re.fullmatch(r"[0-9a-f]{32}", volume["id"])
    assert volume["project_id"] == project_id
    assert volume["title"] == "第一卷"
    assert volume["description"] is None
    assert volume["order"] == 1
    assert volume["chapter_count"] == 0


def test_volume_migration_uses_nanoid_generator() -> None:
    migration = importlib.import_module(
        "app.storage.migrations.versions.048_add_volumes_and_chapter_volume_id"
    )

    assert migration.generate_id is generate_id
    assert not hasattr(migration, "uuid4")


@pytest.mark.asyncio
async def test_create_chapter_requires_volume_id(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"title": "第一章"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chapter_tree_groups_chapters_by_volume(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    first_volume = await _default_volume(client, project_id)
    second_response = await client.post(
        f"/api/v1/projects/{project_id}/volumes",
        json={"title": "第二卷", "description": "下半部"},
    )
    assert second_response.status_code == 201
    second_volume = second_response.json()

    first_chapter = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": first_volume["id"], "title": "第一章"},
    )
    second_chapter = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": second_volume["id"], "title": "第二卷第一章"},
    )
    assert first_chapter.status_code == 201
    assert second_chapter.status_code == 201

    response = await client.get(f"/api/v1/projects/{project_id}/chapters")

    assert response.status_code == 200
    data = response.json()
    assert data["total_chapters"] == 2
    assert [volume["title"] for volume in data["volumes"]] == ["第一卷", "第二卷"]
    assert data["volumes"][0]["chapter_count"] == 1
    assert data["volumes"][0]["chapters"][0]["volume_id"] == first_volume["id"]
    assert data["volumes"][0]["chapters"][0]["order"] == 1
    assert data["volumes"][1]["chapter_count"] == 1
    assert data["volumes"][1]["chapters"][0]["volume_id"] == second_volume["id"]
    assert data["volumes"][1]["chapters"][0]["order"] == 1


@pytest.mark.asyncio
async def test_delete_non_empty_volume_requires_cascade(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    volume = await _default_volume(client, project_id)
    chapter_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume["id"], "title": "第一章"},
    )
    assert chapter_response.status_code == 201

    response = await client.delete(f"/api/v1/volumes/{volume['id']}")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_volume_with_cascade_deletes_chapters(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    volume = await _default_volume(client, project_id)
    second_response = await client.post(
        f"/api/v1/projects/{project_id}/volumes",
        json={"title": "第二卷"},
    )
    assert second_response.status_code == 201
    chapter_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume["id"], "title": "第一章"},
    )
    chapter_id = chapter_response.json()["id"]

    response = await client.delete(f"/api/v1/volumes/{volume['id']}?cascade=true")

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/chapters/{chapter_id}")).status_code == 404


@pytest.mark.asyncio
async def test_delete_last_volume_is_rejected(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    volume = await _default_volume(client, project_id)

    response = await client.delete(f"/api/v1/volumes/{volume['id']}?cascade=true")

    assert response.status_code == 409
    assert "至少需要保留一个卷" in response.json()["detail"]


@pytest.mark.asyncio
async def test_move_chapter_to_volume_appends_to_target(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_id = await _create_project(client)
    source_volume = await _default_volume(client, project_id)
    target_response = await client.post(
        f"/api/v1/projects/{project_id}/volumes",
        json={"title": "第二卷"},
    )
    target_volume = target_response.json()

    source_chapter_ids: list[str] = []
    for title in ["源一", "源二"]:
        response = await client.post(
            f"/api/v1/projects/{project_id}/chapters",
            json={"volume_id": source_volume["id"], "title": title},
        )
        source_chapter_ids.append(response.json()["id"])
    target_chapter = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": target_volume["id"], "title": "目标一"},
    )

    response = await client.post(
        f"/api/v1/chapters/{source_chapter_ids[0]}/move-to-volume",
        json={"volume_id": target_volume["id"]},
    )

    assert response.status_code == 200
    moved = response.json()
    assert moved["volume_id"] == target_volume["id"]
    assert moved["order"] == 2

    tree = (await client.get(f"/api/v1/projects/{project_id}/chapters")).json()
    source_chapters = tree["volumes"][0]["chapters"]
    target_chapters = tree["volumes"][1]["chapters"]
    assert source_chapters == [
        {
            **source_chapters[0],
            "id": source_chapter_ids[1],
            "order": 1,
            "volume_id": source_volume["id"],
        }
    ]
    assert [chapter["id"] for chapter in target_chapters] == [
        target_chapter.json()["id"],
        source_chapter_ids[0],
    ]
    assert [chapter["order"] for chapter in target_chapters] == [1, 2]

    events = (
        await session.execute(
            select(WritingActivityEvent).where(
                col(WritingActivityEvent.chapter_id) == source_chapter_ids[0],
                col(WritingActivityEvent.operation) == "move_to_volume",
            )
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].source == "user"
    assert events[0].word_delta == 0


@pytest.mark.asyncio
async def test_move_chapter_to_volume_marks_retrieval_state_stale(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_id = await _create_project(client)
    source_volume = await _default_volume(client, project_id)
    target_response = await client.post(
        f"/api/v1/projects/{project_id}/volumes",
        json={"title": "第二卷"},
    )
    target_volume = target_response.json()
    chapter_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={
            "volume_id": source_volume["id"],
            "title": "第一章",
            "content": "正文",
        },
    )
    chapter = chapter_response.json()
    state = RetrievalChapterIndexState(
        project_id=project_id,
        chapter_id=chapter["id"],
        index_key=f"chapters:{project_id}",
        status="ready",
        source_hash=compute_chapter_source_hash(chapter["content"]),
        embedding_model_ref_id="model-1",
        chunk_count=1,
    )
    session.add(state)
    await session.commit()

    response = await client.post(
        f"/api/v1/chapters/{chapter['id']}/move-to-volume",
        json={"volume_id": target_volume["id"]},
    )

    assert response.status_code == 200
    await session.refresh(state)
    assert state.status == "stale"
