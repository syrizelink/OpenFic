# -*- coding: utf-8 -*-
"""Uji API tokoh."""

from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.character import Character


def make_image_file(color: str = "red") -> bytes:
    """Membuat gambar avatar untuk uji."""
    buffer = BytesIO()
    image = Image.new("RGB", (64, 64), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def create_project(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/v1/projects", data={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def create_character(
    client: AsyncClient,
    project_id: str,
    name: str,
    description: str = "",
    image: bytes | None = None,
) -> dict:
    files = None
    if image is not None:
        files = {"image": ("avatar.png", image, "image/png")}
    response = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        data={"name": name, "description": description},
        files=files,
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_create_character_with_image_returns_image_url(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Uji Tokoh")

    character = await create_character(
        client,
        project_id,
        "Lina",
        "Deskripsi tokoh utama",
        make_image_file(),
    )

    assert character["project_id"] == project_id
    assert character["name"] == "Lina"
    assert character["description"] == "Deskripsi tokoh utama"
    assert character["image_url"].startswith("/character-images/")
    assert character["is_favorited"] is False
    assert "created_at" in character
    assert "updated_at" in character


@pytest.mark.asyncio
async def test_create_character_generates_numbered_name_when_duplicate(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Nama Ganda Buat")
    await create_character(client, project_id, "Tokoh Tanpa Nama")

    duplicate = await create_character(client, project_id, "Tokoh Tanpa Nama")

    assert duplicate["name"] == "Tokoh Tanpa Nama (2)"


@pytest.mark.asyncio
async def test_create_character_rejects_description_over_line_limit(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Batas Panjang Tokoh")

    response = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        data={"name": "Tokoh Melebihi Batas", "description": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    characters = (await client.get(f"/api/v1/projects/{project_id}/characters")).json()
    assert characters["total"] == 0


@pytest.mark.asyncio
async def test_update_character_rejects_duplicate_name(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Nama Ganda Perbarui")
    first = await create_character(client, project_id, "Lina")
    second = await create_character(client, project_id, "Guntur")

    response = await client.patch(
        f"/api/v1/characters/{second['id']}",
        data={"name": first["name"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Nama tokoh sudah ada"


@pytest.mark.asyncio
async def test_update_character_rejects_description_over_line_limit(
    client: AsyncClient,
) -> None:
    project_id = await create_project(client, "Proyek Batas Panjang Perbarui Tokoh")
    character = await create_character(client, project_id, "Tokoh Asli", "Deskripsi asli")

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"description": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    unchanged = await client.get(f"/api/v1/characters/{character['id']}")
    assert unchanged.json()["description"] == "Deskripsi asli"


@pytest.mark.asyncio
async def test_list_characters_is_scoped_by_project(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek A")
    other_project_id = await create_project(client, "Proyek B")
    await create_character(client, project_id, "Tokoh Proyek A")
    await create_character(client, other_project_id, "Tokoh Proyek B")

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Tokoh Proyek A"
    assert data["items"][0]["project_id"] == project_id
    assert "token_count" in data["items"][0]
    assert "description" not in data["items"][0]


@pytest.mark.asyncio
async def test_list_characters_orders_by_updated_at_desc(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Pengurutan")
    first = await create_character(client, project_id, "Dibuat Awal")
    second = await create_character(client, project_id, "Dibuat Kemudian")

    update_response = await client.patch(
        f"/api/v1/characters/{first['id']}",
        data={"name": "Baru Disunting"},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["Baru Disunting", second["name"]]


@pytest.mark.asyncio
async def test_list_characters_returns_all_project_characters(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_id = await create_project(client, "Proyek Daftar Tokoh Lengkap")
    session.add_all(
        [
            Character(project_id=project_id, name=f"Tokoh {index}")
            for index in range(101)
        ]
    )
    await session.flush()

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 101
    assert len(data["items"]) == 101


@pytest.mark.asyncio
async def test_update_character_favorite_state(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Favorit")
    character = await create_character(client, project_id, "Tokoh Dapat Difavoritkan")

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"is_favorited": "true"},
    )

    assert response.status_code == 200
    assert response.json()["is_favorited"] is True


@pytest.mark.asyncio
async def test_batch_favorite_characters_is_scoped_by_project(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Favorit Massal")
    other_project_id = await create_project(client, "Proyek Favorit Massal Lain")
    first = await create_character(client, project_id, "Tokoh Satu")
    second = await create_character(client, project_id, "Tokoh Dua")
    external = await create_character(client, other_project_id, "Tokoh Eksternal")

    response = await client.post(
        f"/api/v1/projects/{project_id}/characters/batch/favorite",
        json={"character_ids": [first["id"], second["id"], external["id"]], "is_favorited": True},
    )

    assert response.status_code == 200
    assert response.json() == {"updated_count": 2}
    list_response = await client.get(f"/api/v1/projects/{project_id}/characters")
    assert list_response.status_code == 200
    assert {item["id"]: item["is_favorited"] for item in list_response.json()["items"]} == {
        first["id"]: True,
        second["id"]: True,
    }
    external_response = await client.get(f"/api/v1/characters/{external['id']}")
    assert external_response.status_code == 200
    assert external_response.json()["is_favorited"] is False


@pytest.mark.asyncio
async def test_batch_delete_characters_is_scoped_by_project(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Hapus Massal")
    other_project_id = await create_project(client, "Proyek Hapus Massal Lain")
    first = await create_character(client, project_id, "Hapus Satu")
    second = await create_character(client, project_id, "Hapus Dua")
    external = await create_character(client, other_project_id, "Tokoh Hapus Eksternal")

    response = await client.post(
        f"/api/v1/projects/{project_id}/characters/batch/delete",
        json={"character_ids": [first["id"], second["id"], external["id"]]},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted_count": 2}
    list_response = await client.get(f"/api/v1/projects/{project_id}/characters")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []
    external_response = await client.get(f"/api/v1/characters/{external['id']}")
    assert external_response.status_code == 200


@pytest.mark.asyncio
async def test_list_characters_places_favorites_first_then_updated_desc(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Urutan Favorit")
    favorite_old = await create_character(client, project_id, "Favorit Lama")
    normal_recent = await create_character(client, project_id, "Biasa Baru")
    favorite_recent = await create_character(client, project_id, "Favorit Baru")

    old_favorite_response = await client.patch(
        f"/api/v1/characters/{favorite_old['id']}",
        data={"is_favorited": "true"},
    )
    assert old_favorite_response.status_code == 200
    recent_favorite_response = await client.patch(
        f"/api/v1/characters/{favorite_recent['id']}",
        data={"is_favorited": "true"},
    )
    assert recent_favorite_response.status_code == 200

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == [favorite_recent["name"], favorite_old["name"], normal_recent["name"]]


@pytest.mark.asyncio
async def test_search_characters_returns_name_and_description_matches(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Cari Tokoh")
    other_project_id = await create_project(client, "Proyek Cari Lain")
    first = await create_character(client, project_id, "Lina", "Baris pertama\nMenyukai belati perak")
    await create_character(client, project_id, "Perak Agung", "Deskripsi biasa")
    await create_character(client, other_project_id, "Tokoh Perak Eksternal", "Tidak boleh muncul di hasil")

    response = await client.get(
        f"/api/v1/projects/{project_id}/characters/search",
        params={"q": "perak"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_characters"] == 2
    assert data["total_matches"] == 2
    results_by_name = {item["character_name"]: item for item in data["results"]}
    assert results_by_name["Lina"]["character_id"] == first["id"]
    assert results_by_name["Lina"]["matches"][0] == {
        "line_number": 2,
        "line_text": "Menyukai belati perak",
    }
    assert results_by_name["Perak Agung"]["matches"][0] == {
        "line_number": 0,
        "line_text": "Perak Agung",
    }


@pytest.mark.asyncio
async def test_update_character_refreshes_updated_at(client: AsyncClient) -> None:
    project_id = await create_project(client, "Proyek Waktu Pembaruan")
    character = await create_character(client, project_id, "Nama Asli")

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"name": "Nama Baru", "description": "Deskripsi baru"},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Nama Baru"
    assert updated["description"] == "Deskripsi baru"
    assert updated["updated_at"] > character["updated_at"]


@pytest.mark.asyncio
async def test_replace_character_image_deletes_old_file(
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import settings as app_settings

    monkeypatch.setattr(app_settings.settings, "character_images_dir", tmp_path)
    project_id = await create_project(client, "Proyek Ganti Avatar")
    character = await create_character(client, project_id, "Punya Avatar", image=make_image_file("red"))
    old_filename = character["image_url"].split("/character-images/", 1)[1].split("?", 1)[0]
    old_file = tmp_path / old_filename
    assert old_file.exists()

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"name": character["name"]},
        files={"image": ("avatar.png", make_image_file("blue"), "image/png")},
    )

    assert response.status_code == 200
    new_filename = response.json()["image_url"].split("/character-images/", 1)[1].split("?", 1)[0]
    assert new_filename != old_filename
    assert not old_file.exists()
    assert (tmp_path / new_filename).exists()


@pytest.mark.asyncio
async def test_delete_character_deletes_image_file(
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import settings as app_settings

    monkeypatch.setattr(app_settings.settings, "character_images_dir", tmp_path)
    project_id = await create_project(client, "Proyek Hapus Avatar")
    character = await create_character(client, project_id, "Akan Dihapus", image=make_image_file())
    filename = character["image_url"].split("/character-images/", 1)[1].split("?", 1)[0]
    image_file = tmp_path / filename
    assert image_file.exists()

    response = await client.delete(f"/api/v1/characters/{character['id']}")

    assert response.status_code == 204
    assert not image_file.exists()


@pytest.mark.asyncio
async def test_missing_project_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/missing-project/characters")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_character_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/characters/missing-character")

    assert response.status_code == 404
