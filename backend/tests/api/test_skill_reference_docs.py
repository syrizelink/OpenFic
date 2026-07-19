# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient


async def _create_skill(client: AsyncClient, name: str = "测试技能") -> str:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": name,
            "summary": "简述",
            "content": "技能内容",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_reference_docs(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)

    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "参考文档一", "content": "内容一"},
    )
    assert create_response.status_code == 201
    doc = create_response.json()
    assert doc["title"] == "参考文档一"
    assert doc["content"] == "内容一"
    assert doc["tokens"] > 0

    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "参考文档二", "content": ""},
    )

    list_response = await client.get(f"/api/v1/skills/{skill_db_id}/reference-docs")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 2
    assert items[0]["title"] == "参考文档一"


@pytest.mark.asyncio
async def test_builtin_skill_reference_docs_are_loaded_from_yaml(client: AsyncClient) -> None:
    skill_id = "builtin-skill--continue-chapter"

    list_response = await client.get(f"/api/v1/skills/{skill_id}/reference-docs")
    assert list_response.status_code == 200
    items = list_response.json()
    assert [item["title"] for item in items] == ["续写检查清单", "上下文读取指引"]

    create_response = await client.post(
        f"/api/v1/skills/{skill_id}/reference-docs",
        json={"title": "不可新增", "content": ""},
    )
    assert create_response.status_code == 400


@pytest.mark.asyncio
async def test_update_reference_doc(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "原标题", "content": "原内容"},
    )
    doc_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_id}",
        json={"title": "新标题", "content": "新内容"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "新标题"
    assert data["content"] == "新内容"
    assert data["tokens"] > 0


@pytest.mark.asyncio
async def test_delete_reference_doc(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "待删除", "content": ""},
    )
    doc_id = create_response.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_id}"
    )
    assert delete_response.status_code == 204

    list_response = await client.get(f"/api/v1/skills/{skill_db_id}/reference-docs")
    assert list_response.json() == []


@pytest.mark.asyncio
async def test_reference_doc_not_found_for_other_skill(client: AsyncClient) -> None:
    skill_a = await _create_skill(client, "技能A")
    skill_b = await _create_skill(client, "技能B")

    create_response = await client.post(
        f"/api/v1/skills/{skill_a}/reference-docs",
        json={"title": "属于A", "content": ""},
    )
    doc_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_b}/reference-docs/{doc_id}",
        json={"title": "篡改"},
    )
    assert update_response.status_code == 404

    delete_response = await client.delete(
        f"/api/v1/skills/{skill_b}/reference-docs/{doc_id}"
    )
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_reference_doc_skill_not_found(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/skills/nonexistent-skill/reference-docs",
        json={"title": "标题", "content": ""},
    )
    assert create_response.status_code == 404

    list_response = await client.get("/api/v1/skills/nonexistent-skill/reference-docs")
    assert list_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_skill_cascades_reference_docs(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "参考文档", "content": "内容"},
    )

    delete_skill_response = await client.delete(f"/api/v1/skills/{skill_db_id}")
    assert delete_skill_response.status_code == 204

    list_response = await client.get(f"/api/v1/skills/{skill_db_id}/reference-docs")
    assert list_response.status_code == 404


@pytest.mark.asyncio
async def test_create_reference_doc_dedupes_duplicate_title(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)

    first = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "新建参考文档", "content": ""},
    )
    assert first.status_code == 201
    assert first.json()["title"] == "新建参考文档"

    second = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "新建参考文档", "content": ""},
    )
    assert second.status_code == 201
    assert second.json()["title"] == "新建参考文档 (2)"

    third = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "新建参考文档", "content": ""},
    )
    assert third.status_code == 201
    assert third.json()["title"] == "新建参考文档 (3)"


@pytest.mark.asyncio
async def test_create_reference_doc_keeps_unique_title(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "文档A", "content": ""},
    )

    response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "文档B", "content": ""},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "文档B"


@pytest.mark.asyncio
async def test_update_reference_doc_title_conflict(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "文档一", "content": ""},
    )
    create_b = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "文档二", "content": ""},
    )
    doc_b_id = create_b.json()["id"]

    conflict_response = await client.patch(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_b_id}",
        json={"title": "文档一"},
    )
    assert conflict_response.status_code == 409


@pytest.mark.asyncio
async def test_update_reference_doc_keeps_same_title(client: AsyncClient) -> None:
    skill_db_id = await _create_skill(client)
    create_response = await client.post(
        f"/api/v1/skills/{skill_db_id}/reference-docs",
        json={"title": "文档", "content": ""},
    )
    doc_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_db_id}/reference-docs/{doc_id}",
        json={"title": "文档", "content": "新内容"},
    )
    assert update_response.status_code == 200
