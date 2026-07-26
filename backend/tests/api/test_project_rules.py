# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", data={"title": "项目规则测试"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_update_and_list_project_rules(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    create_response = await client.post(
        f"/api/v1/projects/{project_id}/rules",
        json={
            "title": "文风",
            "content": "本项目使用古风文体",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["project_id"] == project_id
    assert created["title"] == "文风"
    assert created["content"] == "本项目使用古风文体"

    rule_id = created["id"]
    update_response = await client.patch(
        f"/api/v1/projects/{project_id}/rules/{rule_id}",
        json={
            "title": "叙事文风",
            "content": "本项目使用第一人称古风文体",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "叙事文风"
    assert updated["content"] == "本项目使用第一人称古风文体"

    list_response = await client.get(f"/api/v1/projects/{project_id}/rules")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "叙事文风"


@pytest.mark.asyncio
async def test_project_rules_isolated_by_project(client: AsyncClient) -> None:
    project_a = await _create_project(client)
    project_b = await _create_project(client)

    create_response = await client.post(
        f"/api/v1/projects/{project_a}/rules",
        json={"title": "规则A", "content": "只属于项目A"},
    )
    assert create_response.status_code == 201
    rule_id = create_response.json()["id"]

    list_b = await client.get(f"/api/v1/projects/{project_b}/rules")
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0

    get_via_b = await client.get(f"/api/v1/projects/{project_b}/rules/{rule_id}")
    assert get_via_b.status_code == 404

    delete_via_b = await client.delete(f"/api/v1/projects/{project_b}/rules/{rule_id}")
    assert delete_via_b.status_code == 404


@pytest.mark.asyncio
async def test_project_rules_reorder_and_delete(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    first = await client.post(
        f"/api/v1/projects/{project_id}/rules",
        json={"title": "规则1", "content": "内容1"},
    )
    second = await client.post(
        f"/api/v1/projects/{project_id}/rules",
        json={"title": "规则2", "content": "内容2"},
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    reorder_response = await client.post(
        f"/api/v1/projects/{project_id}/rules/reorder",
        json={"rule_ids": [second_id, first_id]},
    )
    assert reorder_response.status_code == 200

    list_response = await client.get(f"/api/v1/projects/{project_id}/rules")
    items = list_response.json()["items"]
    assert [item["id"] for item in items] == [second_id, first_id]

    delete_response = await client.delete(f"/api/v1/projects/{project_id}/rules/{first_id}")
    assert delete_response.status_code == 204

    list_response = await client.get(f"/api/v1/projects/{project_id}/rules")
    assert list_response.json()["total"] == 1


@pytest.mark.asyncio
async def test_project_rules_requires_existing_project(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/projects/nonexistent/rules",
        json={"title": "规则", "content": "内容"},
    )
    assert response.status_code == 404

    list_response = await client.get("/api/v1/projects/nonexistent/rules")
    assert list_response.status_code == 404
