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


@pytest.mark.asyncio
async def test_agent_composer_items_returns_recent_items_by_kind(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    volume_id = (await client.get(f"/api/v1/projects/{project_id}/volumes")).json()[0]["id"]

    skills = []
    for index in range(6):
        response = await client.post(
            "/api/v1/skills",
            json={
                "name": f"技能 {index + 1}",
                "summary": "技能说明",
                "content": "技能内容",
                "is_enabled": True,
            },
        )
        assert response.status_code == 201
        skills.append(response.json())

    chapters = []
    notes = []
    world_info = await client.get(f"/api/v1/projects/{project_id}/world-info")
    assert world_info.status_code == 200
    world_info_id = world_info.json()["id"]
    entries = []
    for index in range(6):
        chapter = await client.post(
            f"/api/v1/projects/{project_id}/chapters",
            json={"volume_id": volume_id, "title": f"章节 {index + 1}"},
        )
        note = await client.post(
            f"/api/v1/projects/{project_id}/notes",
            json={"title": f"笔记 {index + 1}"},
        )
        entry = await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"条目 {index + 1}"},
        )
        assert chapter.status_code == 201
        assert note.status_code == 201
        assert entry.status_code == 201
        chapters.append(chapter.json())
        notes.append(note.json())
        entries.append(entry.json())

    response = await client.get(f"/api/v1/projects/{project_id}/agent-composer-items")

    assert response.status_code == 200
    data = response.json()
    assert len(data["skills"]) == 5
    assert len(data["chapters"]) == 5
    assert len(data["notes"]) == 5
    assert len(data["world_info_entries"]) == 5
    assert data["skills"][0]["kind"] == "skill"
    assert data["skills"][0]["id"] in {skill["id"] for skill in skills}
    assert data["chapters"][0]["id"] in {chapter["id"] for chapter in chapters}
    assert data["notes"][0]["id"] in {note["id"] for note in notes}
    assert data["world_info_entries"][0]["id"] in {entry["id"] for entry in entries}
