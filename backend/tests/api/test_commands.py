import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", data={"title": "Command 测试项目"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_skill_commands_search_all_enabled_skills(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    enabled = await client.post(
        "/api/v1/skills",
        json={
            "name": "小说人物设计",
            "summary": "设计人物",
            "content": "完整技能内容",
            "is_enabled": True,
        },
    )
    disabled = await client.post(
        "/api/v1/skills",
        json={
            "name": "小说人物禁用",
            "summary": "不应出现",
            "content": "完整技能内容",
            "is_enabled": False,
        },
    )
    assert enabled.status_code == 201
    assert disabled.status_code == 201

    response = await client.get(
        f"/api/v1/projects/{project_id}/commands",
        params={"kind": "skill", "query": "人物"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert any(
        item["id"] == enabled.json()["id"]
        and item["name"] == enabled.json()["name"]
        and item["description"] == "设计人物"
        for item in items
    )
    assert all(item["name"] != "小说人物禁用" for item in items)
