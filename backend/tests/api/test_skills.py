# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_skills(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "测试技能",
            "summary": "简述",
            "skill_id": "test-skill",
            "content": "技能内容",
            "is_enabled": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["skill_id"] == "test-skill"
    assert data["is_enabled"] is True
    assert data["is_complete"] is True
    assert "order_index" not in data

    list_response = await client.get("/api/v1/skills")
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_create_skill_with_empty_skill_id(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "新建技能",
            "summary": "",
            "skill_id": "",
            "content": "",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["skill_id"] == ""
    assert data["is_complete"] is False
    assert data["is_enabled"] is False


@pytest.mark.asyncio
async def test_incomplete_skill_cannot_be_enabled(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "测试技能",
            "summary": "",
            "skill_id": "bad-skill",
            "content": "",
            "is_enabled": True,
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_toggle_skill(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/skills",
        json={
            "name": "测试技能",
            "summary": "简述",
            "skill_id": "toggle-skill",
            "content": "技能内容",
        },
    )
    skill_db_id = create_response.json()["id"]

    toggle_response = await client.post(f"/api/v1/skills/{skill_db_id}/toggle")
    assert toggle_response.status_code == 200
    assert toggle_response.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_reorder_skills_route_removed(client: AsyncClient) -> None:
    reorder_resp = await client.post(
        "/api/v1/skills/reorder",
        json={"skill_ids": ["skill-a", "skill-b"]},
    )
    assert reorder_resp.status_code == 405
