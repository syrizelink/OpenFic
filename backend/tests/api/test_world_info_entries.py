# -*- coding: utf-8 -*-
"""
WorldInfo Entry API 测试。
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def world_info_id(client: AsyncClient) -> str:
    """创建项目并返回项目唯一世界书 ID。"""
    project_resp = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_resp.json()["id"]
    world_info_resp = await client.get(f"/api/v1/projects/{project_id}/world-info")
    return world_info_resp.json()["id"]


@pytest.mark.asyncio
async def test_create_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试创建条目。"""
    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={
            "name": "测试条目",
            "content": "条目内容",
            "token_count": 10,
            "is_enabled": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试条目"
    assert data["content"] == "条目内容"
    assert data["token_count"] == 10
    assert data["is_enabled"] is True
    assert data["uid"] == 1
    assert data["order"] == 1


@pytest.mark.asyncio
async def test_create_multiple_entries(client: AsyncClient, world_info_id: str) -> None:
    """测试创建多个条目，验证 UID 和 order 自增。"""
    resp1 = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "条目1"},
    )
    assert resp1.json()["uid"] == 1
    assert resp1.json()["order"] == 1

    resp2 = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "条目2"},
    )
    assert resp2.json()["uid"] == 2
    assert resp2.json()["order"] == 2


@pytest.mark.asyncio
async def test_create_entry_uses_unique_name_suffix(
    client: AsyncClient, world_info_id: str
) -> None:
    """创建同名条目时自动追加序号。"""
    first = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "新条目"},
    )
    second = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "新条目"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["name"] == "新条目"
    assert second.json()["name"] == "新条目 (1)"


@pytest.mark.asyncio
async def test_update_entry_rejects_duplicate_name(
    client: AsyncClient, world_info_id: str
) -> None:
    """条目重命名不能改成已有名称。"""
    first = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物"},
    )
    second = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "地点"},
    )

    response = await client.patch(
        f"/api/v1/world-info-entries/{second.json()['id']}",
        json={"name": first.json()["name"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "世界书条目名称已存在: 人物"


@pytest.mark.asyncio
async def test_list_entries(client: AsyncClient, world_info_id: str) -> None:
    """测试获取条目列表。"""
    for i in range(3):
        await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"条目 {i + 1}"},
        )

    response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_get_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试获取单个条目。"""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "测试条目", "content": "条目内容"},
    )
    entry_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == entry_id
    assert data["name"] == "测试条目"


@pytest.mark.asyncio
async def test_update_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试更新条目。"""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "原名称", "content": "原内容"},
    )
    entry_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/world-info-entries/{entry_id}",
        json={"name": "新名称", "content": "新内容"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "新名称"
    assert data["content"] == "新内容"


@pytest.mark.asyncio
async def test_delete_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试删除条目。"""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "待删除条目"},
    )
    entry_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/world-info-entries/{entry_id}")
    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试切换条目开关状态。"""
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "测试条目", "is_enabled": True},
    )
    entry_id = create_resp.json()["id"]

    response = await client.post(f"/api/v1/world-info-entries/{entry_id}/toggle")
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False

    response = await client.post(f"/api/v1/world-info-entries/{entry_id}/toggle")
    assert response.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_preview_world_info_import(client: AsyncClient) -> None:
    """测试预览 SillyTavern 世界书导入。"""
    content = '{"entries":{"0":{"uid":0,"key":["alpha"],"keysecondary":[],"comment":"名称","content":"内容","constant":true,"selective":true,"disable":false,"order":100}}}'.encode("utf-8")

    response = await client.post(
        "/api/v1/world-info/import/preview",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["entry_count"] == 1
    assert data["enabled_count"] == 1
    assert data["entries"][0]["name"] == "名称"
    assert data["entries"][0]["content_preview"] == "内容"


@pytest.mark.asyncio
async def test_import_world_info_entries_stream_append_overwrites_same_name(
    client: AsyncClient, world_info_id: str
) -> None:
    """追加导入时按名称覆盖已有条目。"""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物", "content": "旧内容", "is_enabled": False},
    )
    content = '{"entries":{"0":{"uid":0,"comment":"人物","content":"新内容","disable":false,"order":100},"1":{"uid":1,"comment":"背景","content":"世界观","disable":true,"order":101}}}'.encode("utf-8")

    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries/import-stream?mode=append",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    list_response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    items = list_response.json()["items"]
    assert [item["name"] for item in items] == ["人物", "背景"]

    detail_response = await client.get(f"/api/v1/world-info-entries/{items[0]['id']}")
    detail = detail_response.json()
    assert detail["name"] == "人物"
    assert detail["content"] == "新内容"
    assert detail["is_enabled"] is True


@pytest.mark.asyncio
async def test_import_world_info_entries_stream_overwrite_clears_existing_entries(
    client: AsyncClient, world_info_id: str
) -> None:
    """覆盖导入时先清空旧条目。"""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物", "content": "旧内容"},
    )
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "地点", "content": "旧地点"},
    )
    content = '{"entries":{"0":{"uid":0,"comment":"背景","content":"新世界观","disable":false,"order":100}}}'.encode("utf-8")

    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries/import-stream?mode=overwrite",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    list_response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    items = list_response.json()["items"]
    assert [item["name"] for item in items] == ["背景"]


@pytest.mark.asyncio
async def test_search_entries(client: AsyncClient, world_info_id: str) -> None:
    """测试搜索条目内容。"""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物", "content": "张三是一个勇敢的战士\n他擅长用剑"},
    )
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "地点", "content": "长安城\n繁华的都市"},
    )

    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries/search",
        params={"q": "战士"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 1
    assert data["total_matches"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["entry_name"] == "人物"


@pytest.mark.asyncio
async def test_search_entries_no_results(client: AsyncClient, world_info_id: str) -> None:
    """测试搜索无结果。"""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物", "content": "张三"},
    )

    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries/search",
        params={"q": "不存在"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 0
    assert data["total_matches"] == 0
    assert len(data["results"]) == 0
