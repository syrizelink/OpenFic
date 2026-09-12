import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", data={"title": "Proyek Uji Command"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_skill_commands_search_all_enabled_skills(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    enabled = await client.post(
        "/api/v1/skills",
        json={
            "name": "Desain Tokoh Novel",
            "summary": "Merancang tokoh",
            "content": "Isi skill lengkap",
            "is_enabled": True,
        },
    )
    disabled = await client.post(
        "/api/v1/skills",
        json={
            "name": "Tokoh Novel Nonaktif",
            "summary": "Tidak boleh muncul",
            "content": "Isi skill lengkap",
            "is_enabled": False,
        },
    )
    assert enabled.status_code == 201
    assert disabled.status_code == 201

    response = await client.get(
        f"/api/v1/projects/{project_id}/commands",
        params={"kind": "skill", "query": "Tokoh"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert any(
        item["id"] == enabled.json()["id"]
        and item["name"] == enabled.json()["name"]
        and item["description"] == "Merancang tokoh"
        for item in items
    )
    assert all(item["name"] != "Tokoh Novel Nonaktif" for item in items)
