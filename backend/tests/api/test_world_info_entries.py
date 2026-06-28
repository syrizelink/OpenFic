# -*- coding: utf-8 -*-
"""
WorldInfo Entry API 测试。
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def world_info_id(client: AsyncClient) -> str:
    """创建世界书，返回世界书 ID。"""
    world_info_resp = await client.post(
        "/api/v1/world-info",
        json={"name": "测试世界书"},
    )
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
    assert "keywords" not in data
    assert "memo" not in data
    assert "tags" not in data
    assert "mode" not in data
    assert "entry_type" not in data
    assert "inject_position" not in data
    assert "scan_depth" not in data


@pytest.mark.asyncio
async def test_create_multiple_entries(client: AsyncClient, world_info_id: str) -> None:
    """测试创建多个条目，验证 UID 和 order 自增。"""
    # 创建第一个条目
    resp1 = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "条目1"},
    )
    assert resp1.json()["uid"] == 1
    assert resp1.json()["order"] == 1

    # 创建第二个条目
    resp2 = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "条目2"},
    )
    assert resp2.json()["uid"] == 2
    assert resp2.json()["order"] == 2


@pytest.mark.asyncio
async def test_list_entries(client: AsyncClient, world_info_id: str) -> None:
    """测试获取条目列表。"""
    # 创建几个条目
    for i in range(3):
        await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"条目 {i + 1}"},
        )

    # 获取列表
    response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_entries_pagination(client: AsyncClient, world_info_id: str) -> None:
    """测试条目列表分页。"""
    # 创建 5 个条目
    for i in range(5):
        await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"条目 {i + 1}"},
        )

    # 获取第一页
    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries?page=1&page_size=2"
    )
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试获取单个条目。"""
    # 创建条目
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "测试条目", "content": "条目内容"},
    )
    entry_id = create_resp.json()["id"]

    # 获取条目
    response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == entry_id
    assert data["name"] == "测试条目"


@pytest.mark.asyncio
async def test_update_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试更新条目。"""
    # 创建条目
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "原名称", "content": "原内容"},
    )
    entry_id = create_resp.json()["id"]

    # 更新条目
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
    # 创建条目
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "待删除条目"},
    )
    entry_id = create_resp.json()["id"]

    # 删除条目
    response = await client.delete(f"/api/v1/world-info-entries/{entry_id}")
    assert response.status_code == 204

    # 确认已删除
    get_response = await client.get(f"/api/v1/world-info-entries/{entry_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_move_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试移动条目。"""
    # 创建 3 个条目
    entries = []
    for i in range(3):
        resp = await client.post(
            f"/api/v1/world-info/{world_info_id}/entries",
            json={"name": f"条目 {i + 1}"},
        )
        entries.append(resp.json())

    # 将第一个条目移动到最后
    response = await client.post(
        f"/api/v1/world-info-entries/{entries[0]['id']}/move",
        json={"new_order": 3},
    )
    assert response.status_code == 200
    assert response.json()["order"] == 3

    # 验证顺序
    list_resp = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    items = list_resp.json()["items"]
    assert items[0]["name"] == "条目 2"
    assert items[1]["name"] == "条目 3"
    assert items[2]["name"] == "条目 1"


@pytest.mark.asyncio
async def test_move_entry_capped_position(
    client: AsyncClient, world_info_id: str
) -> None:
    """测试移动条目到超出范围的位置（会被限制到最大值）。"""
    # 创建条目
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "测试条目"},
    )
    entry_id = create_resp.json()["id"]

    # 移动到超大位置（应该被限制到 max_order）
    response = await client.post(
        f"/api/v1/world-info-entries/{entry_id}/move",
        json={"new_order": 999},
    )
    # 单个条目移动到 999 会被限制到 1
    assert response.status_code == 200
    assert response.json()["order"] == 1


@pytest.mark.asyncio
async def test_toggle_entry(client: AsyncClient, world_info_id: str) -> None:
    """测试切换条目开关状态。"""
    # 创建条目
    create_resp = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "测试条目", "is_enabled": True},
    )
    entry_id = create_resp.json()["id"]
    assert create_resp.json()["is_enabled"] is True

    # 切换开关
    response = await client.post(f"/api/v1/world-info-entries/{entry_id}/toggle")
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False

    # 再次切换
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
    assert "constant_count" not in data
    assert "keyword_count" not in data
    assert data["entries"][0]["name"] == "名称"
    assert data["entries"][0]["content_preview"] == "内容"
    assert "keywords" not in data["entries"][0]
    assert "mode" not in data["entries"][0]


@pytest.mark.asyncio
async def test_import_world_info_entries_stream(
    client: AsyncClient, world_info_id: str
) -> None:
    """测试流式导入 SillyTavern 世界书条目。"""
    content = '{"entries":{"0":{"uid":0,"key":["hero"],"keysecondary":["ignored"],"comment":"人物","content":"主角设定","constant":false,"selective":true,"disable":false,"order":100},"1":{"uid":1,"key":["world"],"keysecondary":[],"comment":"背景","content":"世界观","constant":true,"selective":true,"disable":true,"order":101}}}'.encode("utf-8")

    response = await client.post(
        f"/api/v1/world-info/{world_info_id}/entries/import-stream",
        files={"file": ("worldbook.json", content, "application/json")},
    )

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert '"imported_count": 2' in response.text

    list_response = await client.get(f"/api/v1/world-info/{world_info_id}/entries")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 2
    assert items[0]["name"] == "人物"
    assert items[0]["is_enabled"] is True
    assert "keywords" not in items[0]
    assert "mode" not in items[0]
    assert items[1]["name"] == "背景"
    assert items[1]["is_enabled"] is False
    assert "keywords" not in items[1]
    assert "mode" not in items[1]


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
    assert len(data["results"][0]["matches"]) == 1
    assert data["results"][0]["matches"][0]["line_text"] == "张三是一个勇敢的战士"


@pytest.mark.asyncio
async def test_search_entries_multiple_matches(
    client: AsyncClient, world_info_id: str
) -> None:
    """测试搜索多个匹配项。"""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物", "content": "张三\n李四\n张三丰"},
    )

    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries/search",
        params={"q": "张"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 1
    assert data["total_matches"] == 2
    assert len(data["results"][0]["matches"]) == 2


@pytest.mark.asyncio
async def test_search_entries_no_results(
    client: AsyncClient, world_info_id: str
) -> None:
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


@pytest.mark.asyncio
async def test_search_entries_case_insensitive(
    client: AsyncClient, world_info_id: str
) -> None:
    """测试搜索大小写不敏感。"""
    await client.post(
        f"/api/v1/world-info/{world_info_id}/entries",
        json={"name": "人物", "content": "Hello World"},
    )

    response = await client.get(
        f"/api/v1/world-info/{world_info_id}/entries/search",
        params={"q": "hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 1
    assert data["total_matches"] == 1
