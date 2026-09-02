# -*- coding: utf-8 -*-
"""Note API 端点测试。"""

from io import BytesIO
import zipfile

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
async def test_create_note_rejects_content_over_line_limit(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "超限笔记", "content": "\n".join("内容" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "内容超出限制" in response.json()["detail"]
    notes = (await client.get(f"/api/v1/projects/{project_id}/notes")).json()
    assert notes["total_notes"] == 0


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
async def test_update_note_rejects_content_over_line_limit(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "原笔记", "content": "原内容"},
    )
    note_id = create.json()["id"]

    response = await client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "\n".join("内容" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "内容超出限制" in response.json()["detail"]
    unchanged = await client.get(f"/api/v1/notes/{note_id}")
    assert unchanged.json()["content"] == "原内容"


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
async def test_create_category_rejects_missing_parent(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "无效父分类", "parent_id": "missing-parent"},
    )

    assert response.status_code == 400
    assert "父分类不存在" in response.json()["detail"]


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
async def test_mentions_include_world_info_entry_and_character(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    world_info_resp = await client.get(f"/api/v1/projects/{project_id}/world-info")
    assert world_info_resp.status_code == 200
    world_info_id = world_info_resp.json()["id"]
    entry_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "帝国设定", "content": "背景"},
    )
    assert entry_resp.status_code == 201
    character_resp = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        data={"name": "林夏", "description": "主角"},
    )
    assert character_resp.status_code == 201

    entry_search = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "帝国"},
    )
    assert entry_search.status_code == 200
    entry_items = entry_search.json()["items"]
    assert any(
        item["kind"] == "world_info_entry" and item["title"] == "帝国设定"
        for item in entry_items
    )

    character_search = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "林夏"},
    )
    assert character_search.status_code == 200
    character_items = character_search.json()["items"]
    assert any(
        item["kind"] == "character" and item["title"] == "林夏"
        for item in character_items
    )


@pytest.mark.asyncio
async def test_mentions_kind_filter_world_info_entry_only(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    world_info_resp = await client.get(f"/api/v1/projects/{project_id}/world-info")
    assert world_info_resp.status_code == 200
    world_info_id = world_info_resp.json()["id"]
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "地理设定", "content": "地图"},
    )

    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "设定", "kind": "world_info_entry"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["kind"] == "world_info_entry" for item in items)
    assert any(item["title"] == "地理设定" for item in items)


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


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return output.getvalue()


@pytest.mark.asyncio
async def test_preview_note_import_reads_markdown_file(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import/preview",
        files={"file": ("我的笔记.md", "# 内容", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "file_type": "md",
        "note_count": 1,
        "category_count": 0,
        "ignored_file_count": 0,
    }


@pytest.mark.asyncio
async def test_preview_note_import_ignores_non_markdown_zip_members(
    client: AsyncClient,
) -> None:
    project_id, _ = await _create_project(client)
    archive = _zip_bytes(
        {
            "设定/角色.md": "角色",
            "设定/世界.md": "世界",
            "设定/子分类/地点.md": "地点",
            "设定/封面.png": b"not markdown",
        }
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import/preview",
        files={"file": ("notes.zip", archive, "application/zip")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "file_type": "zip",
        "note_count": 3,
        "category_count": 2,
        "ignored_file_count": 1,
    }


@pytest.mark.asyncio
async def test_preview_note_import_rejects_third_level_category(
    client: AsyncClient,
) -> None:
    project_id, _ = await _create_project(client)
    archive = _zip_bytes({"一级/二级/三级/笔记.md": "内容"})

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import/preview",
        files={"file": ("too-deep.zip", archive, "application/zip")},
    )

    assert response.status_code == 400
    assert "分类层级不能超过两级" in response.json()["detail"]


@pytest.mark.asyncio
async def test_import_notes_rebuilds_zip_categories_from_project_root(
    client: AsyncClient,
) -> None:
    project_id, _ = await _create_project(client)
    archive = _zip_bytes(
        {
            "设定/角色.md": "角色内容",
            "设定/子分类/地点.md": "地点内容",
            "说明.txt": "ignored",
        }
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import",
        files={"file": ("notes.zip", archive, "application/zip")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "file_type": "zip",
        "imported_note_count": 2,
        "imported_category_count": 2,
        "ignored_file_count": 1,
    }

    tree = (await client.get(f"/api/v1/projects/{project_id}/notes")).json()
    assert tree["total_notes"] == 2
    assert len(tree["categories"]) == 1
    assert tree["categories"][0]["title"] == "设定"
    assert tree["categories"][0]["notes"][0]["title"] == "角色"
    assert tree["categories"][0]["categories"][0]["title"] == "子分类"


@pytest.mark.asyncio
async def test_import_markdown_file_creates_root_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import",
        files={"file": ("根笔记.md", "# 正文\n内容", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["imported_note_count"] == 1
    tree = (await client.get(f"/api/v1/projects/{project_id}/notes")).json()
    assert [(note["title"], note["category_id"]) for note in tree["root_notes"]] == [
        ("根笔记", None)
    ]

    note_id = tree["root_notes"][0]["id"]
    note = (await client.get(f"/api/v1/notes/{note_id}")).json()
    assert note["content"] == "# 正文\n内容"


@pytest.mark.asyncio
async def test_export_note_returns_markdown_file(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    note = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "我的笔记", "content": "# 标题\n\n正文"},
    )
    note_id = note.json()["id"]

    response = await client.get(f"/api/v1/notes/{note_id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "filename*=UTF-8''%E6%88%91%E7%9A%84%E7%AC%94%E8%AE%B0.md" in response.headers[
        "content-disposition"
    ]
    assert response.content.decode() == "# 标题\n\n正文"


@pytest.mark.asyncio
async def test_export_category_returns_zip_with_category_folder(
    client: AsyncClient,
) -> None:
    project_id, _ = await _create_project(client)
    parent = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "设定"},
    )
    parent_id = parent.json()["id"]
    child = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "子分类", "parent_id": parent_id},
    )
    child_id = child.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "角色", "category_id": parent_id, "content": "角色内容"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "地点", "category_id": child_id, "content": "地点内容"},
    )

    response = await client.get(f"/api/v1/note-categories/{parent_id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "filename*=UTF-8''%E8%AE%BE%E5%AE%9A.zip" in response.headers[
        "content-disposition"
    ]
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "设定/",
            "设定/角色.md",
            "设定/子分类/",
            "设定/子分类/地点.md",
        }
        assert archive.read("设定/角色.md").decode() == "角色内容"
        assert archive.read("设定/子分类/地点.md").decode() == "地点内容"


@pytest.mark.asyncio
async def test_export_empty_category_keeps_category_folder(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    category = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "空分类"},
    )
    category_id = category.json()["id"]

    response = await client.get(f"/api/v1/note-categories/{category_id}/export")

    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["空分类/"]
