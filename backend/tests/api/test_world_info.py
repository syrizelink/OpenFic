# -*- coding: utf-8 -*-
"""
WorldInfo API 测试。
"""

import pytest
from httpx import AsyncClient


# ============== 世界书测试 ==============


@pytest.mark.asyncio
async def test_create_world_info(client: AsyncClient) -> None:
    """测试创建世界书。"""
    # 先创建项目
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    # 创建世界书（关联项目）
    response = await client.post(
        "/api/v1/world-info",
        json={"name": "测试世界书", "project_id": project_id},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试世界书"
    assert data["project_id"] == project_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_world_info_independent(client: AsyncClient) -> None:
    """测试创建独立世界书（不关联项目）。"""
    response = await client.post(
        "/api/v1/world-info",
        json={"name": "独立世界书"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "独立世界书"
    assert data["project_id"] is None


@pytest.mark.asyncio
async def test_create_world_info_project_not_found(client: AsyncClient) -> None:
    """测试创建世界书时项目不存在。"""
    response = await client.post(
        "/api/v1/world-info",
        json={"name": "测试世界书", "project_id": "nonexistent"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_world_info_duplicate_project(client: AsyncClient) -> None:
    """测试同一项目重复绑定世界书。"""
    # 创建项目
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_resp.json()["id"]

    # 第一次创建世界书
    await client.post(
        "/api/v1/world-info",
        json={"name": "世界书1", "project_id": project_id},
    )

    # 第二次创建世界书绑定同一项目应该失败
    response = await client.post(
        "/api/v1/world-info",
        json={"name": "世界书2", "project_id": project_id},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_world_info(client: AsyncClient) -> None:
    """测试获取世界书列表。"""
    # 创建几个世界书
    for i in range(3):
        await client.post(
            "/api/v1/world-info",
            json={"name": f"世界书 {i + 1}"},
        )

    # 获取列表
    response = await client.get("/api/v1/world-info")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert "items" in data


@pytest.mark.asyncio
async def test_get_world_info(client: AsyncClient) -> None:
    """测试根据 ID 获取世界书。"""
    # 创建世界书
    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "测试世界书"},
    )
    world_info_id = create_resp.json()["id"]

    # 获取世界书
    response = await client.get(f"/api/v1/world-info/{world_info_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == world_info_id
    assert data["name"] == "测试世界书"


@pytest.mark.asyncio
async def test_get_project_world_info(client: AsyncClient) -> None:
    """测试获取项目的世界书。"""
    # 创建项目和世界书
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "测试世界书", "project_id": project_id},
    )
    world_info_id = create_resp.json()["id"]

    # 获取世界书
    response = await client.get(f"/api/v1/projects/{project_id}/world-info")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == world_info_id
    assert data["name"] == "测试世界书"


@pytest.mark.asyncio
async def test_get_project_world_info_not_exists(client: AsyncClient) -> None:
    """测试获取项目的世界书（不存在）。"""
    # 创建项目但不创建世界书
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_resp.json()["id"]

    # 获取世界书
    response = await client.get(f"/api/v1/projects/{project_id}/world-info")
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_update_world_info(client: AsyncClient) -> None:
    """测试更新世界书。"""
    # 创建世界书
    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "原名称"},
    )
    world_info_id = create_resp.json()["id"]

    # 更新世界书
    response = await client.patch(
        f"/api/v1/world-info/{world_info_id}",
        json={"name": "新名称"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "新名称"


@pytest.mark.asyncio
async def test_update_world_info_bind_project(client: AsyncClient) -> None:
    """测试更新世界书绑定项目。"""
    # 创建项目
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_resp.json()["id"]

    # 创建独立世界书
    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "独立世界书"},
    )
    world_info_id = create_resp.json()["id"]
    assert create_resp.json()["project_id"] is None

    # 绑定项目
    response = await client.patch(
        f"/api/v1/world-info/{world_info_id}",
        json={"project_id": project_id},
    )
    assert response.status_code == 200
    assert response.json()["project_id"] == project_id


@pytest.mark.asyncio
async def test_update_world_info_unbind_project(client: AsyncClient) -> None:
    """测试更新世界书解绑项目。"""
    # 创建项目
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_resp.json()["id"]

    # 创建关联世界书
    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "绑定世界书", "project_id": project_id},
    )
    world_info_id = create_resp.json()["id"]
    assert create_resp.json()["project_id"] == project_id

    # 解绑项目
    response = await client.patch(
        f"/api/v1/world-info/{world_info_id}",
        json={"unbind_project": True},
    )
    assert response.status_code == 200
    assert response.json()["project_id"] is None


@pytest.mark.asyncio
async def test_delete_world_info(client: AsyncClient) -> None:
    """测试删除世界书。"""
    # 创建世界书
    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "待删除世界书"},
    )
    world_info_id = create_resp.json()["id"]

    # 删除世界书
    response = await client.delete(f"/api/v1/world-info/{world_info_id}")
    assert response.status_code == 204

    # 确认已删除
    get_response = await client.get(f"/api/v1/world-info/{world_info_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_world_info_cascades_entries(client: AsyncClient) -> None:
    """测试删除世界书时级联删除条目。"""
    # 创建世界书
    create_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "测试世界书"},
    )
    wi_id = create_resp.json()["id"]

    # 创建条目
    entry_resp = await client.post(
        f"/api/v1/world-info/{wi_id}/entries",
        json={"name": "测试条目"},
    )
    entry_id = entry_resp.json()["id"]

    # 删除世界书
    await client.delete(f"/api/v1/world-info/{wi_id}")

    # 验证条目也被删除
    get_response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert get_response.status_code == 404
