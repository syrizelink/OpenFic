# -*- coding: utf-8 -*-
"""
Project API 测试。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    """测试创建项目。"""
    response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说", "description": "这是一个测试小说"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "测试小说"
    assert data["description"] == "这是一个测试小说"
    assert data["word_count"] == 0
    assert data["chapter_count"] == 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_project_without_description(client: AsyncClient) -> None:
    """测试创建不带简介的项目。"""
    response = await client.post(
        "/api/v1/projects",
        data={"title": "无简介小说"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "无简介小说"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_project_empty_title(client: AsyncClient) -> None:
    """测试创建项目时标题为空。"""
    response = await client.post(
        "/api/v1/projects",
        data={"title": ""},
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient) -> None:
    """测试获取空的项目列表。"""
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    """测试获取项目列表。"""
    # 创建几个项目
    for i in range(3):
        await client.post(
            "/api/v1/projects",
            data={"title": f"小说 {i + 1}"},
        )

    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_projects_pagination(client: AsyncClient) -> None:
    """测试项目列表分页。"""
    # 创建 5 个项目
    for i in range(5):
        await client.post(
            "/api/v1/projects",
            data={"title": f"小说 {i + 1}"},
        )

    # 获取第一页
    response = await client.get("/api/v1/projects?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2

    # 获取第二页
    response = await client.get("/api/v1/projects?page=2&page_size=2")
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient) -> None:
    """测试获取项目详情。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说", "description": "测试简介"},
    )
    project_id = create_response.json()["id"]

    # 获取项目
    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["title"] == "测试小说"
    assert data["description"] == "测试简介"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """测试获取不存在的项目。"""
    response = await client.get("/api/v1/projects/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    """测试更新项目。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "原标题", "description": "原简介"},
    )
    project_id = create_response.json()["id"]

    # 更新项目
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        data={"title": "新标题", "description": "新简介"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "新标题"
    assert data["description"] == "新简介"


@pytest.mark.asyncio
async def test_update_project_partial(client: AsyncClient) -> None:
    """测试部分更新项目。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "原标题", "description": "原简介"},
    )
    project_id = create_response.json()["id"]

    # 只更新标题
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        data={"title": "新标题"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "新标题"
    assert data["description"] == "原简介"  # 简介保持不变


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient) -> None:
    """测试更新不存在的项目。"""
    response = await client.patch(
        "/api/v1/projects/nonexistent",
        data={"title": "新标题"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """测试删除项目。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "待删除小说"},
    )
    project_id = create_response.json()["id"]

    # 删除项目
    response = await client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204

    # 确认已删除
    get_response = await client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    """测试删除不存在的项目。"""
    response = await client.delete("/api/v1/projects/nonexistent")
    assert response.status_code == 404
