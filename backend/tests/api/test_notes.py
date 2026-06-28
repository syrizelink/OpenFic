# -*- coding: utf-8 -*-
"""Note API 端点测试。"""

import pytest
from httpx import AsyncClient


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


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "测试笔记", "content": "内容"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "测试笔记"
    assert data["content"] == "内容"
    assert data["project_id"] == project_id
    assert data["is_locked"] is False
    assert data["is_hidden"] is False


@pytest.mark.asyncio
async def test_create_note_in_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    cat_resp = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "设定"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "角色A", "category_id": cat_id},
    )
    assert resp.status_code == 201
    assert resp.json()["category_id"] == cat_id


@pytest.mark.asyncio
async def test_get_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "详情", "content": "正文"},
    )
    note_id = create.json()["id"]
    resp = await client.get(f"/api/v1/notes/{note_id}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "正文"


@pytest.mark.asyncio
async def test_get_note_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/notes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "旧标题", "content": "旧内容"},
    )
    note_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/notes/{note_id}",
        json={"title": "新标题"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"
    assert resp.json()["content"] == "旧内容"


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "待删"},
    )
    note_id = create.json()["id"]
    resp = await client.delete(f"/api/v1/notes/{note_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/notes/{note_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_notes(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "笔记A"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "笔记B"},
    )
    resp = await client.get(f"/api/v1/projects/{project_id}/notes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_notes"] == 2
    assert len(data["root_notes"]) == 2


@pytest.mark.asyncio
async def test_list_notes_project_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/projects/nonexistent/notes")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toggle_note_lock(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "锁定测试"},
    )
    note_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/notes/{note_id}/lock",
        json={"is_locked": True},
    )
    assert resp.status_code == 200
    assert resp.json()["is_locked"] is True


@pytest.mark.asyncio
async def test_toggle_note_hidden(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "隐藏测试"},
    )
    note_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/notes/{note_id}/hidden",
        json={"is_hidden": True},
    )
    assert resp.status_code == 200
    assert resp.json()["is_hidden"] is True


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "设定"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "设定"
    assert resp.json()["parent_id"] is None


@pytest.mark.asyncio
async def test_create_category_third_level_rejected(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    c1 = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "一级"},
    )
    c1_id = c1.json()["id"]
    c2 = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "二级", "parent_id": c1_id},
    )
    c2_id = c2.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "三级", "parent_id": c2_id},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "旧名"},
    )
    cat_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/note-categories/{cat_id}",
        json={"title": "新名"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新名"


@pytest.mark.asyncio
async def test_delete_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "待删"},
    )
    cat_id = create.json()["id"]
    resp = await client.delete(f"/api/v1/note-categories/{cat_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_category_404(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/note-categories/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_move_note_to_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    cat = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "目标"},
    )
    cat_id = cat.json()["id"]
    note = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "移动我"},
    )
    note_id = note.json()["id"]
    resp = await client.post(
        "/api/v1/note-items/move",
        json={
            "kind": "note",
            "item_id": note_id,
            "target_category_id": cat_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["kind"] == "note"
    assert resp.json()["note"]["category_id"] == cat_id


@pytest.mark.asyncio
async def test_move_item_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/note-items/move",
        json={
            "kind": "note",
            "item_id": "nonexistent",
            "target_category_id": None,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mentions_includes_note_kind(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "世界设定", "content": "内容"},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "世界"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(item["kind"] == "note" and item["title"] == "世界设定" for item in items)


@pytest.mark.asyncio
async def test_mentions_hidden_note_absent(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    note = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "隐藏笔记", "content": ""},
    )
    note_id = note.json()["id"]
    await client.patch(
        f"/api/v1/notes/{note_id}/hidden",
        json={"is_hidden": True},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "隐藏"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert not any(
        item["kind"] == "note" and item["title"] == "隐藏笔记" for item in items
    )


@pytest.mark.asyncio
async def test_mentions_kind_filter_note_only(client: AsyncClient) -> None:
    project_id, volume_id = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "设定A", "content": ""},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": "设定相关章", "content": ""},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "设定", "kind": "note"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["kind"] == "note" for item in items)
    assert any(item["title"] == "设定A" for item in items)


@pytest.mark.asyncio
async def test_mentions_includes_note_category_kind(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    cat = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "世界观设定"},
    )
    assert cat.status_code == 201
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "世界观"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        item["kind"] == "note_category" and item["title"] == "世界观设定"
        for item in items
    )


@pytest.mark.asyncio
async def test_mentions_kind_filter_note_category_only(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "角色设定"},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "设定", "kind": "note_category"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["kind"] == "note_category" for item in items)
    assert any(item["title"] == "角色设定" for item in items)


@pytest.mark.asyncio
async def test_mentions_project_404(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/projects/nonexistent/mentions",
        params={"query": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mentions_empty_query_returns_empty(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "某笔记", "content": ""},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "   "},
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": []}
