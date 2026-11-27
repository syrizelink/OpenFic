import pytest
from httpx import AsyncClient

from app.storage.models.project import Project
from app.storage.repos import project_repo


@pytest.mark.asyncio
async def test_quick_prompts_scope_and_crud(client: AsyncClient, session) -> None:
    project = Project(title="项目")
    other = Project(title="其他项目")
    await project_repo.create(session, project)
    await project_repo.create(session, other)
    global_response = await client.post("/api/v1/quick-prompts", json={"command": "global", "content": "全局"})
    project_response = await client.post("/api/v1/quick-prompts", json={"command": "local", "content": "项目", "scope": "project", "project_id": project.id})
    await client.post("/api/v1/quick-prompts", json={"command": "other", "scope": "project", "project_id": other.id})
    assert global_response.status_code == project_response.status_code == 201
    response = await client.get("/api/v1/quick-prompts", params={"project_id": project.id})
    assert {item["command"] for item in response.json()} == {"global", "local"}
    prompt_id = project_response.json()["id"]
    response = await client.put(f"/api/v1/quick-prompts/{prompt_id}", json={"command": "edit", "content": "多行\n内容", "scope": "global"})
    assert response.status_code == 200
    assert response.json()["project_id"] is None
    assert response.json()["content"] == "多行\n内容"
    assert (await client.delete(f"/api/v1/quick-prompts/{prompt_id}")).status_code == 204
    assert (await client.delete(f"/api/v1/quick-prompts/{prompt_id}")).status_code == 404
    assert (await client.post("/api/v1/quick-prompts", json={"command": "bad command"})).status_code == 422
    assert (await client.post("/api/v1/quick-prompts", json={"command": "bad", "scope": "project", "project_id": "missing"})).status_code == 400
