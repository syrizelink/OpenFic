# -*- coding: utf-8 -*-
"""
Chapter API 测试。
"""

import pytest
from httpx import AsyncClient

from app.storage.models.chapter_summary import ChapterSummary
from app.storage.repos.chapter_summary_repo import (
    SUMMARY_STATUS_READY,
    SUMMARY_TYPE_LONG_TERM,
)


async def _create_project(client: AsyncClient) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
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
    """测试创建章节。"""
    project_id, volume_id = await _create_project(client)

    data = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="第一章",
        content="这是第一章的内容。",
    )

    assert data["title"] == "第一章"
    assert data["content"] == "这是第一章的内容。"
    assert data["project_id"] == project_id
    assert data["volume_id"] == volume_id
    assert data["order"] == 1
    assert data["word_count"] > 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_chapter_empty_content(client: AsyncClient) -> None:
    """测试创建空内容的章节。"""
    project_id, volume_id = await _create_project(client)

    data = await _create_chapter(client, project_id, volume_id, title="空章节")

    assert data["title"] == "空章节"
    assert data["content"] == ""
    assert data["word_count"] == 0


@pytest.mark.asyncio
async def test_create_chapter_validation_errors(client: AsyncClient) -> None:
    """测试创建章节时的校验错误。"""
    project_id, volume_id = await _create_project(client)

    empty_title = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": ""},
    )
    missing_volume = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"title": "第一章"},
    )

    assert empty_title.status_code == 422
    assert missing_volume.status_code == 422


@pytest.mark.asyncio
async def test_create_chapter_project_or_volume_not_found(client: AsyncClient) -> None:
    """测试在不存在的项目或卷下创建章节。"""
    missing_project = await client.post(
        "/api/v1/projects/nonexistent/chapters",
        json={"volume_id": "missing", "title": "测试章节"},
    )
    project_id, _volume_id = await _create_project(client)
    missing_volume = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": "missing", "title": "测试章节"},
    )

    assert missing_project.status_code == 404
    assert missing_volume.status_code == 404


@pytest.mark.asyncio
async def test_list_chapters_empty(client: AsyncClient) -> None:
    """测试获取空的卷-章树。"""
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
    """测试获取章节树（精简版，不含正文）。"""
    project_id, volume_id = await _create_project(client)
    for i in range(3):
        await _create_chapter(
            client,
            project_id,
            volume_id,
            title=f"第{i + 1}章",
            content=f"章节{i + 1}的内容",
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
        title="序章",
        content="内容",
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
        title="夜航",
        content="内容",
    )

    response = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "第一卷"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert any(
        item["kind"] == "volume"
        and item["id"] == volume_id
        and item["title"] == "第一卷"
        and item["label"] == "第一卷"
        for item in items
    )
    assert any(
        item["kind"] == "chapter"
        and item["title"] == "夜航"
        and item["label"] == "夜航"
        and item["description"] == "第一卷"
        for item in items
    )


@pytest.mark.asyncio
async def test_get_and_update_chapter(client: AsyncClient) -> None:
    """测试获取和更新章节。"""
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="原标题",
        content="原内容",
    )

    get_response = await client.get(f"/api/v1/chapters/{chapter['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["volume_id"] == volume_id

    update_response = await client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        json={"title": "新标题", "content": "新内容", "word_count": 200},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "新标题"
    assert data["content"] == "新内容"
    assert data["word_count"] == 200


@pytest.mark.asyncio
async def test_chapter_not_found(client: AsyncClient) -> None:
    """测试不存在章节的响应。"""
    get_response = await client.get("/api/v1/chapters/nonexistent")
    update_response = await client.patch(
        "/api/v1/chapters/nonexistent",
        json={"title": "新标题"},
    )
    delete_response = await client.delete("/api/v1/chapters/nonexistent")

    assert get_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_chapter_updates_orders_and_stats(client: AsyncClient) -> None:
    """测试删除章节后顺序和统计更新。"""
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(
            client, project_id, volume_id, title=f"第{i + 1}章", content="内容"
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
async def test_delete_chapter_removes_summary_and_affected_long_term_summaries(
    client: AsyncClient, session
) -> None:
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(
            client,
            project_id,
            volume_id,
            title=f"第{i + 1}章",
            content="内容",
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
                summary=f"章节摘要{chapter['order']}",
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
                summary=f"区间摘要{start_order}-{end_order}",
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
async def test_delete_project_cascades_chapters_and_volumes(
    client: AsyncClient,
) -> None:
    """测试删除项目时级联删除章节和卷。"""
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, title="测试章节")

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/chapters/{chapter['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/volumes/{volume_id}")).status_code == 404


@pytest.mark.asyncio
async def test_reorder_chapters(client: AsyncClient) -> None:
    """测试批量重排章节顺序。"""
    project_id, volume_id = await _create_project(client)
    chapters = [
        await _create_chapter(client, project_id, volume_id, title=f"第{i + 1}章")
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
async def test_reorder_chapters_invalid_chapter(client: AsyncClient) -> None:
    """测试批量重排包含不存在的章节。"""
    project_id, volume_id = await _create_project(client)
    chapter = await _create_chapter(client, project_id, volume_id, title="第一章")

    response = await client.post(
        "/api/v1/chapters/reorder",
        json={"volume_id": volume_id, "chapter_ids": [chapter["id"], "nonexistent"]},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reorder_chapters_wrong_volume(client: AsyncClient) -> None:
    """测试批量重排章节到错误的卷。"""
    project_id, volume_id = await _create_project(client)
    other_volume = (
        await client.post(
            f"/api/v1/projects/{project_id}/volumes",
            json={"title": "第二卷"},
        )
    ).json()

    chapter = await _create_chapter(client, project_id, volume_id, title="第一章")

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
    """测试创建和更新章节时项目统计更新。"""
    project_id, volume_id = await _create_project(client)
    project = await client.get(f"/api/v1/projects/{project_id}")
    assert project.json()["chapter_count"] == 0
    assert project.json()["word_count"] == 0

    chapter = await _create_chapter(
        client,
        project_id,
        volume_id,
        title="第一章",
        content="这是测试内容",
        word_count=100,
    )
    project = await client.get(f"/api/v1/projects/{project_id}")
    assert project.json()["chapter_count"] == 1
    assert project.json()["word_count"] == 100

    await client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        json={"content": "新内容", "word_count": 200},
    )
    project = await client.get(f"/api/v1/projects/{project_id}")
    assert project.json()["chapter_count"] == 1
    assert project.json()["word_count"] == 200
