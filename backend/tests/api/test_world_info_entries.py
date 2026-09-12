# -*- coding: utf-8 -*-
"""
Uji API WorldInfo Entry.
"""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.world_info_entry import WorldInfoEntry


@pytest.fixture
async def world_info_id(client: AsyncClient) -> str:
    """Membuat proyek dan mengembalikan ID buku dunia tunggal milik proyek."""
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    project_id = project_resp.json()["id"]
    world_info_resp = await client.get(f"/api/v1/projects/{project_id}/world-info")
    return world_info_resp.json()["id"]


@pytest.mark.asyncio
async def test_create_entry(client: AsyncClient, world_info_id: str) -> None:
    """Uji pembuatan entri."""
    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={
            "name": "Entri Uji",
            "content": "Isi entri",
            "token_count": 10,
            "is_enabled": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Entri Uji"
    assert data["content"] == "Isi entri"
    assert data["token_count"] == 10
    assert data["is_enabled"] is True
    assert data["uid"] == 1
    assert data["order"] == 1


@pytest.mark.asyncio
async def test_create_entry_rejects_content_over_line_limit(
    client: AsyncClient, world_info_id: str
) -> None:
    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Melebihi Batas", "content": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    entries = (await client.get(f"/api/v1/world-info/{world_info_id}/entries")).json()
    assert entries["total"] == 0


@pytest.mark.asyncio
async def test_create_multiple_entries(client: AsyncClient, world_info_id: str) -> None:
    """Uji pembuatan beberapa entri sekaligus memverifikasi UID dan order bertambah."""
    resp1 = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri 1"},
    )
    assert resp1.json()["uid"] == 1
    assert resp1.json()["order"] == 1

    resp2 = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri 2"},
    )
    assert resp2.json()["uid"] == 2
    assert resp2.json()["order"] == 2


@pytest.mark.asyncio
async def test_create_entry_uses_unique_name_suffix(
    client: AsyncClient, world_info_id: str
) -> None:
    """Saat entri dengan nama sama dibuat, nomor urut ditambahkan otomatis."""
    first = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Baru"},
    )
    second = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Baru"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["name"] == "Entri Baru"
    assert second.json()["name"] == "Entri Baru (1)"


@pytest.mark.asyncio
async def test_update_entry_rejects_duplicate_name(
    client: AsyncClient, world_info_id: str
) -> None:
    """Mengganti nama entri tidak boleh memakai nama yang sudah ada."""
    first = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Tokoh"},
    )
    second = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Lokasi"},
    )

    response = await client.patch(
        f"/api/v1/world-info-entries/{second.json()['id']}",
        json={"name": first.json()["name"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Nama entri buku dunia sudah ada: Tokoh"


@pytest.mark.asyncio
async def test_list_entries(client: AsyncClient, world_info_id: str) -> None:
    """Uji pengambilan daftar entri."""
    for i in range(3):
        await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"Entri {i + 1}"},
        )

    response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_entries_returns_all_world_info_entries(
    client: AsyncClient,
    session: AsyncSession,
    world_info_id: str,
) -> None:
    session.add_all(
        [
            WorldInfoEntry(
                world_info_id=world_info_id,
                uid=index + 1,
                name=f"Entri {index + 1}",
                order=index + 1,
            )
            for index in range(101)
        ]
    )
    await session.flush()

    response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 101
    assert len(data["items"]) == 101


@pytest.mark.asyncio
async def test_move_entry_returns_brief_item(client: AsyncClient, world_info_id: str) -> None:
    entry_ids = []
    for index in range(3):
        response = await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"Entri Pindah {index + 1}", "content": "Isi utama"},
        )
        entry_ids.append(response.json()["id"])

    response = await client.post(
        f"/api/v1/world-info-entries/{entry_ids[0]}/move",
        json={"new_order": 3},
    )

    assert response.status_code == 200
    assert response.json()["id"] == entry_ids[0]
    assert response.json()["order"] == 3
    assert "content" not in response.json()


@pytest.mark.asyncio
async def test_get_entry(client: AsyncClient, world_info_id: str) -> None:
    """Uji pengambilan satu entri."""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Uji", "content": "Isi entri"},
    )
    entry_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == entry_id
    assert data["name"] == "Entri Uji"


@pytest.mark.asyncio
async def test_update_entry(client: AsyncClient, world_info_id: str) -> None:
    """Uji pembaruan entri."""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Nama Asli", "content": "Isi asli"},
    )
    entry_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/world-info-entries/{entry_id}",
        json={"name": "Nama Baru", "content": "Isi baru"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nama Baru"
    assert data["content"] == "Isi baru"


@pytest.mark.asyncio
async def test_update_entry_rejects_content_over_line_limit(
    client: AsyncClient, world_info_id: str
) -> None:
    create_response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Asli", "content": "Isi asli"},
    )
    entry_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/v1/world-info-entries/{entry_id}",
        json={"content": "\n".join("Isi" for _ in range(2001))},
    )

    assert response.status_code == 400
    assert "Konten melebihi batas" in response.json()["detail"]
    unchanged = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert unchanged.json()["content"] == "Isi asli"


@pytest.mark.asyncio
async def test_delete_entry(client: AsyncClient, world_info_id: str) -> None:
    """Uji penghapusan entri."""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Akan Dihapus"},
    )
    entry_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/world-info-entries/{entry_id}")
    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_entry(client: AsyncClient, world_info_id: str) -> None:
    """Uji pengalihan status aktif entri."""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Uji", "is_enabled": True},
    )
    entry_id = create_resp.json()["id"]

    response = await client.post(f"/api/v1/world-info-entries/{entry_id}/toggle")
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False

    response = await client.post(f"/api/v1/world-info-entries/{entry_id}/toggle")
    assert response.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_preview_world_info_import(client: AsyncClient) -> None:
    """Uji pratinjau impor buku dunia SillyTavern."""
    content = '{"entries":{"0":{"uid":0,"key":["alpha"],"keysecondary":[],"comment":"Nama","content":"Isi","constant":true,"selective":true,"disable":false,"order":100}}}'.encode("utf-8")

    response = await client.post(
        "/api/v1/world-info/import/preview",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["entry_count"] == 1
    assert data["enabled_count"] == 1
    assert data["entries"][0]["name"] == "Nama"
    assert data["entries"][0]["content_preview"] == "Isi"


@pytest.mark.asyncio
async def test_import_world_info_entries_stream_append_overwrites_same_name(
    client: AsyncClient, world_info_id: str
) -> None:
    """Saat impor append, entri yang sudah ada ditimpa berdasarkan nama."""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Tokoh", "content": "Isi lama", "is_enabled": False},
    )
    content = '{"entries":{"0":{"uid":0,"comment":"Tokoh","content":"Isi baru","disable":false,"order":100},"1":{"uid":1,"comment":"Latar","content":"Pandangan dunia","disable":true,"order":101}}}'.encode("utf-8")

    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries/import-stream?mode=append",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    list_response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    items = list_response.json()["items"]
    assert [item["name"] for item in items] == ["Tokoh", "Latar"]

    detail_response = await client.get(f"/api/v1/world-info-entries/{items[0]['id']}")
    detail = detail_response.json()
    assert detail["name"] == "Tokoh"
    assert detail["content"] == "Isi baru"
    assert detail["is_enabled"] is True


@pytest.mark.asyncio
async def test_import_world_info_entries_stream_overwrite_clears_existing_entries(
    client: AsyncClient, world_info_id: str
) -> None:
    """Saat impor overwrite, entri lama dibersihkan lebih dahulu."""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Tokoh", "content": "Isi lama"},
    )
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Lokasi", "content": "Lokasi lama"},
    )
    content = '{"entries":{"0":{"uid":0,"comment":"Latar","content":"Pandangan dunia baru","disable":false,"order":100}}}'.encode("utf-8")

    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries/import-stream?mode=overwrite",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    list_response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    items = list_response.json()["items"]
    assert [item["name"] for item in items] == ["Latar"]


@pytest.mark.asyncio
async def test_import_world_info_entries_stream_overwrite_rejects_oversized_content(
    client: AsyncClient, world_info_id: str
) -> None:
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Lama", "content": "Isi lama"},
    )
    content = json.dumps(
        {
            "entries": {
                "0": {
                    "uid": 0,
                    "comment": "Entri Melebihi Batas",
                    "content": "\n".join("Isi" for _ in range(2001)),
                    "disable": False,
                    "order": 100,
                }
            }
        }
    ).encode("utf-8")

    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries/import-stream?mode=overwrite",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert any(
        event["type"] == "error" and "Konten melebihi batas" in event["message"]
        for event in events
    )
    assert all(event["type"] != "complete" for event in events)
    list_response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    items = list_response.json()["items"]
    assert [item["name"] for item in items] == ["Entri Lama"]
    entry_response = await client.get(f"/api/v1/world-info-entries/{items[0]['id']}")
    assert entry_response.json()["content"] == "Isi lama"


@pytest.mark.asyncio
async def test_search_entries(client: AsyncClient, world_info_id: str) -> None:
    """Uji pencarian isi entri."""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Tokoh", "content": "Adi adalah seorang pendekar pemberani\nDia mahir memakai pedang"},
    )
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Lokasi", "content": "Kota Anggara\nKota metropolitan yang ramai"},
    )

    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries/search",
        params={"q": "pendekar"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 1
    assert data["total_matches"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["entry_name"] == "Tokoh"


@pytest.mark.asyncio
async def test_search_entries_no_results(client: AsyncClient, world_info_id: str) -> None:
    """Uji pencarian tanpa hasil."""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Tokoh", "content": "Adi"},
    )

    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries/search",
        params={"q": "tidak ada"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 0
    assert data["total_matches"] == 0
    assert len(data["results"]) == 0
