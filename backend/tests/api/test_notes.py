# -*- coding: utf-8 -*-
"""Uji endpoint API Note."""

from io import BytesIO
import zipfile

import pytest
from httpx import AsyncClient


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


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Catatan Uji", "content": "Isi"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Catatan Uji"
    assert data["content"] == "Isi"
    assert data["project_id"] == project_id
    assert data["is_locked"] is False
    assert data["is_hidden"] is False


@pytest.mark.asyncio
async def test_create_note_rejects_content_over_line_limit(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Catatan Melebihi Batas", "content": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    notes = (await client.get(f"/api/v1/projects/{project_id}/notes")).json()
    assert notes["total_notes"] == 0


@pytest.mark.asyncio
async def test_create_note_in_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    cat_resp = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Setelan"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Tokoh A", "category_id": cat_id},
    )
    assert resp.status_code == 201
    assert resp.json()["category_id"] == cat_id


@pytest.mark.asyncio
async def test_get_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Detail", "content": "Isi utama"},
    )
    note_id = create.json()["id"]
    resp = await client.get(f"/api/v1/notes/{note_id}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "Isi utama"


@pytest.mark.asyncio
async def test_get_note_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/notes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Judul Lama", "content": "Isi lama"},
    )
    note_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/notes/{note_id}",
        json={"title": "Judul Baru"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Judul Baru"
    assert resp.json()["content"] == "Isi lama"


@pytest.mark.asyncio
async def test_update_note_rejects_content_over_line_limit(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Catatan Asli", "content": "Isi asli"},
    )
    note_id = create.json()["id"]

    response = await client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    unchanged = await client.get(f"/api/v1/notes/{note_id}")
    assert unchanged.json()["content"] == "Isi asli"


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Akan Dihapus"},
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
        json={"title": "Catatan A"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Catatan B"},
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
        json={"title": "Uji Terkunci"},
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
        json={"title": "Uji Tersembunyi"},
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
        json={"title": "Setelan"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Setelan"
    assert resp.json()["parent_id"] is None


@pytest.mark.asyncio
async def test_create_category_third_level_rejected(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    c1 = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Tingkat Satu"},
    )
    c1_id = c1.json()["id"]
    c2 = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Tingkat Dua", "parent_id": c1_id},
    )
    c2_id = c2.json()["id"]
    resp = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Tingkat Tiga", "parent_id": c2_id},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_category_rejects_missing_parent(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Kategori Induk Tidak Valid", "parent_id": "missing-parent"},
    )

    assert response.status_code == 400
    assert "Kategori induk tidak ada" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Nama Lama"},
    )
    cat_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/note-categories/{cat_id}",
        json={"title": "Nama Baru"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Nama Baru"


@pytest.mark.asyncio
async def test_delete_category(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    create = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Akan Dihapus"},
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
        json={"title": "Tujuan"},
    )
    cat_id = cat.json()["id"]
    note = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Pindahkan Aku"},
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
        json={"title": "Setelan Dunia", "content": "Isi"},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Dunia"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(item["kind"] == "note" and item["title"] == "Setelan Dunia" for item in items)


@pytest.mark.asyncio
async def test_mentions_hidden_note_absent(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    note = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Catatan Tersembunyi", "content": ""},
    )
    note_id = note.json()["id"]
    await client.patch(
        f"/api/v1/notes/{note_id}/hidden",
        json={"is_hidden": True},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Tersembunyi"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert not any(
        item["kind"] == "note" and item["title"] == "Catatan Tersembunyi" for item in items
    )


@pytest.mark.asyncio
async def test_mentions_kind_filter_note_only(client: AsyncClient) -> None:
    project_id, volume_id = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Setelan A", "content": ""},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": "Bab Terkait Setelan", "content": ""},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Setelan", "kind": "note"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["kind"] == "note" for item in items)
    assert any(item["title"] == "Setelan A" for item in items)


@pytest.mark.asyncio
async def test_mentions_includes_note_category_kind(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    cat = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Setelan Pandangan Dunia"},
    )
    assert cat.status_code == 201
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Pandangan Dunia"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        item["kind"] == "note_category" and item["title"] == "Setelan Pandangan Dunia"
        for item in items
    )


@pytest.mark.asyncio
async def test_mentions_kind_filter_note_category_only(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Setelan Tokoh"},
    )
    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Setelan", "kind": "note_category"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["kind"] == "note_category" for item in items)
    assert any(item["title"] == "Setelan Tokoh" for item in items)


@pytest.mark.asyncio
async def test_mentions_include_world_info_entry_and_character(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    world_info_resp = await client.get(f"/api/v1/projects/{project_id}/world-info")
    assert world_info_resp.status_code == 200
    world_info_id = world_info_resp.json()["id"]
    entry_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Setelan Kekaisaran", "content": "Latar"},
    )
    assert entry_resp.status_code == 201
    character_resp = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        data={"name": "Lina", "description": "Tokoh utama"},
    )
    assert character_resp.status_code == 201

    entry_search = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Kekaisaran"},
    )
    assert entry_search.status_code == 200
    entry_items = entry_search.json()["items"]
    assert any(
        item["kind"] == "world_info_entry" and item["title"] == "Setelan Kekaisaran"
        for item in entry_items
    )

    character_search = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Lina"},
    )
    assert character_search.status_code == 200
    character_items = character_search.json()["items"]
    assert any(
        item["kind"] == "character" and item["title"] == "Lina"
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
        json={"name": "Setelan Geografi", "content": "Peta"},
    )

    resp = await client.get(
        f"/api/v1/projects/{project_id}/mentions",
        params={"query": "Setelan", "kind": "world_info_entry"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["kind"] == "world_info_entry" for item in items)
    assert any(item["title"] == "Setelan Geografi" for item in items)


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
        json={"title": "Suatu Catatan", "content": ""},
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
        files={"file": ("Catatan Saya.md", "# Isi", "text/markdown")},
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
            "Setelan/Tokoh.md": "Tokoh",
            "Setelan/Dunia.md": "Dunia",
            "Setelan/Subkategori/Lokasi.md": "Lokasi",
            "Setelan/Sampul.png": b"not markdown",
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
    archive = _zip_bytes({"Tingkat1/Tingkat2/Tingkat3/Catatan.md": "Isi"})

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import/preview",
        files={"file": ("too-deep.zip", archive, "application/zip")},
    )

    assert response.status_code == 400
    assert "tidak boleh lebih dari dua" in response.json()["detail"]


@pytest.mark.asyncio
async def test_import_notes_rebuilds_zip_categories_from_project_root(
    client: AsyncClient,
) -> None:
    project_id, _ = await _create_project(client)
    archive = _zip_bytes(
        {
            "Setelan/Tokoh.md": "Isi tokoh",
            "Setelan/Subkategori/Lokasi.md": "Isi lokasi",
            "Keterangan.txt": "ignored",
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
    assert tree["categories"][0]["title"] == "Setelan"
    assert tree["categories"][0]["notes"][0]["title"] == "Tokoh"
    assert tree["categories"][0]["categories"][0]["title"] == "Subkategori"


@pytest.mark.asyncio
async def test_import_markdown_file_creates_root_note(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/notes/import",
        files={"file": ("Catatan Akar.md", "# Isi utama\nIsi", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["imported_note_count"] == 1
    tree = (await client.get(f"/api/v1/projects/{project_id}/notes")).json()
    assert [(note["title"], note["category_id"]) for note in tree["root_notes"]] == [
        ("Catatan Akar", None)
    ]

    note_id = tree["root_notes"][0]["id"]
    note = (await client.get(f"/api/v1/notes/{note_id}")).json()
    assert note["content"] == "# Isi utama\nIsi"


@pytest.mark.asyncio
async def test_export_note_returns_markdown_file(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    note = await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Catatan Saya", "content": "# Judul\n\nIsi utama"},
    )
    note_id = note.json()["id"]

    response = await client.get(f"/api/v1/notes/{note_id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "filename*=UTF-8''Catatan%20Saya.md" in response.headers[
        "content-disposition"
    ]
    assert response.content.decode() == "# Judul\n\nIsi utama"


@pytest.mark.asyncio
async def test_export_category_returns_zip_with_category_folder(
    client: AsyncClient,
) -> None:
    project_id, _ = await _create_project(client)
    parent = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Setelan"},
    )
    parent_id = parent.json()["id"]
    child = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Subkategori", "parent_id": parent_id},
    )
    child_id = child.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Tokoh", "category_id": parent_id, "content": "Isi tokoh"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/notes",
        json={"title": "Lokasi", "category_id": child_id, "content": "Isi lokasi"},
    )

    response = await client.get(f"/api/v1/note-categories/{parent_id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "filename*=UTF-8''Setelan.zip" in response.headers[
        "content-disposition"
    ]
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "Setelan/",
            "Setelan/Tokoh.md",
            "Setelan/Subkategori/",
            "Setelan/Subkategori/Lokasi.md",
        }
        assert archive.read("Setelan/Tokoh.md").decode() == "Isi tokoh"
        assert archive.read("Setelan/Subkategori/Lokasi.md").decode() == "Isi lokasi"


@pytest.mark.asyncio
async def test_export_empty_category_keeps_category_folder(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    category = await client.post(
        f"/api/v1/projects/{project_id}/note-categories",
        json={"title": "Kategori Kosong"},
    )
    category_id = category.json()["id"]

    response = await client.get(f"/api/v1/note-categories/{category_id}/export")

    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["Kategori Kosong/"]
