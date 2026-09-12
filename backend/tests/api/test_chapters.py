# -*- coding: utf-8 -*-
"""
Uji API Chapter.
"""

import pytest
from httpx import AsyncClient

from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.repos.chapter_summary_repo import (
    SUMMARY_STATUS_READY,
    SUMMARY_TYPE_LONG_TERM,
)
from app.storage.services import chapter_service


async def _create_project(client: AsyncClient) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]
    volumes = (await client.get(f"/api/v1/projects/{project_id}/volumes")).json()
    assert len(volumes) == 1
    return project_id, volumes[0]["id"]


async def _create_chapter(
    client: AsyncClient,
    project_id: str,
    volume_id: str,
    *,
    title: str,
    content: str = "",
    word_count: int | None = None,
) -> dict:
    payload: dict = {"volume_id": volume_id, "title": title, "content": content}
    if word_count is not None:
        payload["word_count"] = word_count
    response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def _chapters_from_tree(tree: dict) -> list[dict]:
    return [chapter for volume in tree["volumes"] for chapter in volume["chapters"]]


@pytest.mark.asyncio
async def test_create_chapter(client: AsyncClient) -> None:
    """Uji pembuatan bab."""
    project_id, volume_id = await _create_project(client)

    data = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="Bab 1",
        content="Ini adalah isi bab pertama.",
    )

    assert data["title"] == "Bab 1"
    assert data["content"] == "Ini adalah isi bab pertama."
    assert data["project_id"] == project_id
    assert data["volume_id"] == volume_id
    assert data["order"] == 1
    assert data["word_count"] > 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_chapter_empty_content(client: AsyncClient) -> None:
    """Uji pembuatan bab dengan isi kosong."""
    project_id, volume_id = await _create_project(client)

    data = await _create_chapter(client, project_id, volume_id, title="Bab Kosong")

    assert data["title"] == "Bab Kosong"
    assert data["content"] == ""
    assert data["word_count"] == 0


@pytest.mark.asyncio
async def test_create_chapter_rejects_content_over_line_limit(client: AsyncClient) -> None:
    project_id, volume_id = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={
            "volume_id": volume_id,
            "title": "Bab Melebihi Batas",
            "content": "\n".join("Isi" for _ in range(2001)),
        },
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    tree = (await client.get(f"/api/v1/projects/{project_id}/chapters")).json()
    assert tree["total_chapters"] == 0


@pytest.mark.asyncio
async def test_create_chapter_validation_errors(client: AsyncClient) -> None:
    """Uji error validasi saat membuat bab."""
    project_id, volume_id = await _create_project(client)

    empty_title = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": ""},
    )
    missing_volume = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"title": "Bab 1"},
    )

    assert empty_title.status_code == 422
    assert missing_volume.status_code == 422


@pytest.mark.asyncio
async def test_create_chapter_project_or_volume_not_found(client: AsyncClient) -> None:
    """Uji pembuatan bab pada proyek atau volume yang tidak ada."""
    missing_project = await client.post(
        "/api/v1/projects/nonexistent/chapters",
        json={"volume_id": "missing", "title": "Bab Uji"},
    )
    project_id, _volume_id = await _create_project(client)
    missing_volume = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": "missing", "title": "Bab Uji"},
    )

    assert missing_project.status_code == 404
    assert missing_volume.status_code == 404


@pytest.mark.asyncio
async def test_list_chapters_empty(client: AsyncClient) -> None:
    """Uji pengambilan pohon volume-bab yang kosong."""
    project_id, volume_id = await _create_project(client)

    response = await client.get(f"/api/v1/projects/{project_id}/chapters")

    assert response.status_code == 200
    data = response.json()
    assert data["total_chapters"] == 0
    assert len(data["volumes"]) == 1
    assert data["volumes"][0]["id"] == volume_id
    assert data["volumes"][0]["chapters"] == []


@pytest.mark.asyncio
async def test_list_chapters(client: AsyncClient) -> None:
    """Uji pengambilan pohon bab (versi ringkas, tanpa isi utama)."""
    project_id, volume_id = await _create_project(client)
    for i in range(3):
        await _create_chapter(
            client,
            project_id,
            volume_id,
            title=f"Bab {i + 1}",
            content=f"Isi bab {i + 1}",
        )

    response = await client.get(f"/api/v1/projects/{project_id}/chapters")

    assert response.status_code == 200
    data = response.json()
    items = data["volumes"][0]["chapters"]
    assert data["total_chapters"] == 3
    assert [item["order"] for item in items] == [1, 2, 3]
    assert all("content" not in item for item in items)
    item = items[0]
    assert item["volume_id"] == volume_id
    for key in [
        "id",
        "project_id",
        "title",
        "word_count",
        "order",
        "created_at",
        "updated_at",
    ]:
        assert key in item


@pytest.mark.asyncio
async def test_search_mention_candidates_returns_empty_items_for_blank_query(
    client: AsyncClient,
) -> None:
    project_id, volume_id = await _create_project(client)
    await _create_chapter(
        client,
        project_id,
        volume_id,
        title="Prolog",
        content="Isi",
    )

    response = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "   "},
    )

    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.asyncio
async def test_search_mention_candidates_matches_volume_and_chapter_titles(
    client: AsyncClient,
) -> None:
    project_id, volume_id = await _create_project(client)
    await _create_chapter(
        client,
        project_id,
        volume_id,
        title="Pelayaran Malam",
        content="Isi",
    )

    response = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Volume 1"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert any(
        item["kind"] == "volume"
        and item["id"] == volume_id
        and item["title"] == "Volume 1"
        and item["label"] == "Volume 1"
        for item in items
    )
    assert any(
        item["kind"] == "chapter"
        and item["title"] == "Pelayaran Malam"
        and item["label"] == "Pelayaran Malam"
        and item["description"] == "Volume 1"
        for item in items
    )


@pytest.mark.asyncio
async def test_get_and_update_chapter(client: AsyncClient) -> None:
    """Uji pengambilan dan pembaruan bab."""
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="Judul Asli",
        content="Isi asli",
    )

    get_response = await client.get(f"/api/v1/chapters/{chapter['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["volume_id"] == volume_id

    update_response = await client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        json={"title": "Judul Baru", "content": "Isi baru", "word_count": 200},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "Judul Baru"
    assert data["content"] == "Isi baru"
    assert data["word_count"] == 200


@pytest.mark.asyncio
async def test_update_chapter_rejects_content_over_line_limit(client: AsyncClient) -> None:
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="Bab Asli",
        content="Isi asli",
    )

    response = await client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        json={"content": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    unchanged = await client.get(f"/api/v1/chapters/{chapter['id']}")
    assert unchanged.json()["content"] == "Isi asli"


@pytest.mark.asyncio
async def test_chapter_not_found(client: AsyncClient) -> None:
    """Uji respons untuk bab yang tidak ada."""
    get_response = await client.get("/api/v1/chapters/nonexistent")
    update_response = await client.patch(
        "/api/v1/chapters/nonexistent",
        json={"title": "Judul Baru"},
    )
    delete_response = await client.delete("/api/v1/chapters/nonexistent")

    assert get_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_chapter_updates_orders_and_stats(client: AsyncClient) -> None:
    """Uji pembaruan urutan dan statistik setelah bab dihapus."""
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(
            client, project_id, volume_id, title=f"Bab {i + 1}", content="Isi"
        )
        for i in range(3)
    ]

    response = await client.delete(f"/api/v1/chapters/{chapters[1]['id']}")

    assert response.status_code == 204
    tree = (await client.get(f"/api/v1/projects/{project_id}/chapters")).json()
    items = tree["volumes"][0]["chapters"]
    assert [item["id"] for item in items] == [chapters[0]["id"], chapters[2]["id"]]
    assert [item["order"] for item in items] == [1, 2]
    assert tree["volumes"][0]["chapter_count"] == 2
    project = (await client.get(f"/api/v1/projects/{project_id}")).json()
    assert project["chapter_count"] == 2


@pytest.mark.asyncio
async def test_delete_reordered_chapter_updates_orders(client: AsyncClient) -> None:
    """Uji penghapusan bab dapat merapatkan urutan bab yang sudah diurut ulang dengan aman."""
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(client, project_id, volume_id, title=f"Bab {i + 1}")
        for i in range(4)
    ]
    reordered_ids = [
        chapters[0]["id"],
        chapters[2]["id"],
        chapters[1]["id"],
        chapters[3]["id"],
    ]
    reorder_response = await client.post(
        "/api/v1/chapters/reorder",
        json={"volume_id": volume_id, "chapter_ids": reordered_ids},
    )
    assert reorder_response.status_code == 200

    response = await client.delete(f"/api/v1/chapters/{chapters[0]['id']}")

    assert response.status_code == 204
    tree = (await client.get(f"/api/v1/projects/{project_id}/chapters")).json()
    items = tree["volumes"][0]["chapters"]
    assert [item["id"] for item in items] == reordered_ids[1:]
    assert [item["order"] for item in items] == [1, 2, 3]


@pytest.mark.asyncio
async def test_delete_chapter_removes_summary_and_affected_long_term_summaries(
    client: AsyncClient, session
) -> None:
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(
            client,
            project_id,
            volume_id,
            title=f"Bab {i + 1}",
            content="Isi",
            word_count=800,
        )
        for i in range(30)
    ]

    for chapter in chapters:
        session.add(
            ChapterSummary(
                project_id=project_id,
                summary_type="chapter",
                status=SUMMARY_STATUS_READY,
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                summary=f"Ringkasan bab {chapter['order']}",
                source_content_normalized=chapter["content"],
            )
        )

    for start_order, end_order in ((1, 10), (11, 20), (21, 30)):
        session.add(
            ChapterSummary(
                project_id=project_id,
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_READY,
                start_order=start_order,
                end_order=end_order,
                summary=f"Ringkasan rentang {start_order}-{end_order}",
            )
        )
    await session.commit()

    response = await client.delete(f"/api/v1/chapters/{chapters[10]['id']}")

    assert response.status_code == 204

    chapter_list = await client.get(
        f"/api/v1/projects/{project_id}/chapter-context/summaries/chapters"
    )
    assert chapter_list.status_code == 200
    assert all(
        item["chapter_id"] != chapters[10]["id"]
        for item in chapter_list.json()["items"]
    )

    long_term_list = await client.get(
        f"/api/v1/projects/{project_id}/chapter-context/summaries/long-term"
    )
    assert long_term_list.status_code == 200
    assert [
        (item["start_order"], item["end_order"])
        for item in long_term_list.json()["items"]
    ] == [(1, 10)]


@pytest.mark.asyncio
async def test_delete_chapter_in_later_volume_keeps_prior_long_term_summaries(
    client: AsyncClient, session
) -> None:
    project_id, first_volume_id = await _create_project(client)
    second_volume_response = await client.post(
        f"/api/v1/projects/{project_id}/volumes",
        json={"title": "Volume 2"},
    )
    assert second_volume_response.status_code == 201
    second_volume_id = second_volume_response.json()["id"]

    for order in range(10):
        await _create_chapter(
            client,
            project_id,
            first_volume_id,
            title=f"Bab {order + 1}",
            content="Isi",
            word_count=800,
        )
    second_volume_chapters = [
        await _create_chapter(
            client,
            project_id,
            second_volume_id,
            title=f"Bab {order + 1}",
            content="Isi",
            word_count=800,
        )
        for order in range(10)
    ]

    for start_order, end_order in ((1, 10), (11, 20)):
        session.add(
            ChapterSummary(
                project_id=project_id,
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_READY,
                start_order=start_order,
                end_order=end_order,
                summary=f"Ringkasan rentang {start_order}-{end_order}",
            )
        )
    await session.commit()

    response = await client.delete(
        f"/api/v1/chapters/{second_volume_chapters[0]['id']}"
    )

    assert response.status_code == 204
    long_term_list = await client.get(
        f"/api/v1/projects/{project_id}/chapter-context/summaries/long-term"
    )
    assert long_term_list.status_code == 200
    assert [
        (item["start_order"], item["end_order"])
        for item in long_term_list.json()["items"]
    ] == [(1, 10)]


@pytest.mark.asyncio
async def test_delete_project_cascades_chapters_and_volumes(
    client: AsyncClient,
) -> None:
    """Uji penghapusan proyek menghapus bab dan volume secara berantai."""
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, title="Bab Uji")

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/chapters/{chapter['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/volumes/{volume_id}")).status_code == 404


@pytest.mark.asyncio
async def test_reorder_chapters(client: AsyncClient) -> None:
    """Uji pengurutan ulang bab secara massal."""
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(client, project_id, volume_id, title=f"Bab {i + 1}")
        for i in range(4)
    ]

    new_order = [
        chapters[2]["id"],
        chapters[0]["id"],
        chapters[3]["id"],
        chapters[1]["id"],
    ]
    response = await client.post(
        "/api/v1/chapters/reorder",
        json={"volume_id": volume_id, "chapter_ids": new_order},
    )

    assert response.status_code == 200
    result = response.json()
    assert [item["id"] for item in result] == new_order
    assert [item["order"] for item in result] == [1, 2, 3, 4]

    tree = (await client.get(f"/api/v1/projects/{project_id}/chapters")).json()
    items = _chapters_from_tree(tree)
    assert [item["id"] for item in items] == new_order
    assert [item["order"] for item in items] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_reorder_only_updates_chapters_whose_order_changed(client: AsyncClient, session, monkeypatch):
    project = Project(title="Proyek Uji Pengurutan")
    volume = Volume(project_id=project.id, title="Volume 1", order=1)
    chapters = [
        Chapter(project_id=project.id, volume_id=volume.id, title=f"Bab {index}", order=index)
        for index in range(1, 4)
    ]
    session.add(project)
    session.add(volume)
    session.add_all(chapters)
    await session.flush()

    captured_orders: dict[str, int] = {}

    async def capture_orders(_session, orders):
        captured_orders.update(orders)
        return None

    monkeypatch.setattr(chapter_service.chapter_repo, "update_orders", capture_orders)

    await chapter_service.reorder_chapters(
        session,
        volume.id,
        [chapters[1].id, chapters[0].id, chapters[2].id],
    )

    assert captured_orders == {chapters[1].id: 1, chapters[0].id: 2}


@pytest.mark.asyncio
async def test_reorder_chapters_invalid_chapter(client: AsyncClient) -> None:
    """Uji pengurutan ulang massal yang memuat bab tidak ada."""
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, title="Bab 1")

    response = await client.post(
        "/api/v1/chapters/reorder",
        json={"volume_id": volume_id, "chapter_ids": [chapter["id"], "nonexistent"]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reorder_chapters_wrong_volume(client: AsyncClient) -> None:
    """Uji pengurutan ulang bab ke volume yang salah."""
    project_id, volume_id = await _create_project(client)
    other_volume = (
        await client.post(
            f"/api/v1/projects/{project_id}/volumes",
            json={"title": "Volume 2"},
        )
    ).json()

    chapter = await _create_chapter(client, project_id, volume_id, title="Bab 1")

    response = await client.post(
        "/api/v1/chapters/reorder",
        json={
            "volume_id": other_volume["id"],
            "chapter_ids": [chapter["id"]],
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_project_stats_update_on_chapter_create_and_update(
    client: AsyncClient,
) -> None:
    """Uji pembaruan statistik proyek saat bab dibuat dan diperbarui."""
    project_id, volume_id = await _create_project(client)
    project = await client.get(f"/api/v1/projects/{project_id}")
    assert project.json()["chapter_count"] == 0
    assert project.json()["word_count"] == 0

    chapter = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="Bab 1",
        content="Ini adalah isi uji",
        word_count=100,
    )
    project = await client.get(f"/api/v1/projects/{project_id}")
    assert project.json()["chapter_count"] == 1
    assert project.json()["word_count"] == 100

    await client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        json={"content": "Isi baru", "word_count": 200},
    )
    project = await client.get(f"/api/v1/projects/{project_id}")
    assert project.json()["chapter_count"] == 1
    assert project.json()["word_count"] == 200
