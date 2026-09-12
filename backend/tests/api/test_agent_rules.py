# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_update_and_list_agent_rules_with_title(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/agent-rules",
        json={
            "title": "Bahasa Balasan",
            "content": "Gunakan bahasa Indonesia saat membalas",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == "Bahasa Balasan"
    assert created["content"] == "Gunakan bahasa Indonesia saat membalas"
    assert created["scope"] == "global"
    assert created["project_id"] is None
    assert created["token_count"] > 0

    rule_id = created["id"]
    update_response = await client.patch(
        f"/api/v1/agent-rules/{rule_id}",
        json={
            "title": "Bahasa Keluaran",
            "content": "Selalu balas dengan bahasa Indonesia",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Bahasa Keluaran"
    assert updated["content"] == "Selalu balas dengan bahasa Indonesia"

    list_response = await client.get("/api/v1/agent-rules")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["title"] == "Bahasa Keluaran"
    assert payload["items"][0]["content"] == "Selalu balas dengan bahasa Indonesia"


@pytest.mark.asyncio
async def test_create_project_rule_and_list_scopes(client: AsyncClient, session) -> None:
    from app.storage.repos import project_repo
    from app.storage.models.project import Project

    project = Project(title="Proyek Uji")
    await project_repo.create(session, project)
    await session.flush()

    global_create = await client.post(
        "/api/v1/agent-rules",
        json={
            "title": "Aturan Baru",
            "content": "",
        },
    )
    assert global_create.status_code == 201

    create_response = await client.post(
        "/api/v1/agent-rules",
        json={
            "title": "Aturan Proyek",
            "content": "Hanya berlaku pada proyek ini",
            "scope": "project",
            "project_id": project.id,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["scope"] == "project"
    assert created["project_id"] == project.id

    scopes_response = await client.get("/api/v1/agent-rules/scopes")
    assert scopes_response.status_code == 200
    scopes = scopes_response.json()["items"]
    assert scopes[0]["scope"] == "global"
    assert scopes[0]["rule_count"] == 1
    project_scope = next(s for s in scopes if s["project_id"] == project.id)
    assert project_scope["rule_count"] == 1

    list_response = await client.get(
        "/api/v1/agent-rules",
        params={"scope": "project", "project_id": project.id},
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Aturan Proyek"


@pytest.mark.asyncio
async def test_create_project_rule_without_project_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agent-rules",
        json={
            "title": "Aturan Proyek Tidak Valid",
            "content": "Tidak ada",
            "scope": "project",
            "project_id": "nonexistent",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_all_rules_puts_global_first(client: AsyncClient, session) -> None:
    from app.storage.repos import project_repo
    from app.storage.models.project import Project
    from app.storage.services import agent_rule_service

    project = Project(title="Proyek Uji Pengurutan")
    await project_repo.create(session, project)
    await session.flush()

    await client.post(
        "/api/v1/agent-rules",
        json={"title": "Aturan Proyek A", "content": "AAA", "scope": "project", "project_id": project.id},
    )
    await client.post(
        "/api/v1/agent-rules",
        json={"title": "Aturan Global A", "content": "GGG"},
    )
    await client.post(
        "/api/v1/agent-rules",
        json={"title": "Aturan Proyek B", "content": "BBB", "scope": "project", "project_id": project.id},
    )

    rules = await agent_rule_service.list_all_rules(session, project_id=project.id)
    scopes = [rule.scope for rule in rules]
    assert scopes == ["global", "project", "project"]