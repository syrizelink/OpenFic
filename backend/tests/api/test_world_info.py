# -*- coding: utf-8 -*-
"""
Uji API WorldInfo.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_project_world_info_auto_creates(client: AsyncClient) -> None:
    """Buku dunia dibuat otomatis saat dibaca per proyek."""
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    response = await client.get(f"/api/v1/projects/{project_id}/world-info")

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert "id" in data


@pytest.mark.asyncio
async def test_get_project_world_info_returns_same_world_info(client: AsyncClient) -> None:
    """Pembacaan berulang pada proyek yang sama mengembalikan buku dunia yang sama."""
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    project_id = project_resp.json()["id"]

    first = await client.get(f"/api/v1/projects/{project_id}/world-info")
    second = await client.get(f"/api/v1/projects/{project_id}/world-info")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["project_id"] == project_id


@pytest.mark.asyncio
async def test_get_project_world_info_project_not_found(client: AsyncClient) -> None:
    """Mengembalikan 404 saat proyek tidak ada."""
    response = await client.get("/api/v1/projects/nonexistent/world-info")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_world_info_endpoint_is_disabled(client: AsyncClient) -> None:
    """Pembuatan buku dunia secara langsung tidak diizinkan."""
    response = await client.post(
        "/api/v1/world-info",
        json={"name": "Buku Dunia Uji"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_world_info_endpoint_is_disabled(client: AsyncClient) -> None:
    """Pembaruan entitas buku dunia itu sendiri tidak diizinkan."""
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    world_info_resp = await client.get(
        f"/api/v1/projects/{project_resp.json()['id']}/world-info"
    )
    world_info_id = world_info_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/world-info/{world_info_id}",
        json={"name": "Nama Baru"},
    )

    assert response.status_code == 405


@pytest.mark.asyncio
async def test_delete_world_info_cascades_entries(client: AsyncClient) -> None:
    """Menghapus buku dunia menghapus entrinya secara berantai."""
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    project_id = project_resp.json()["id"]
    world_info_resp = await client.get(f"/api/v1/projects/{project_id}/world-info")
    world_info_id = world_info_resp.json()["id"]

    entry_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "Entri Uji"},
    )
    entry_id = entry_resp.json()["id"]

    response = await client.delete(f"/api/v1/world-info/{world_info_id}")
    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert get_response.status_code == 404
