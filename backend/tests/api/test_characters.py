# -*- coding: utf-8 -*-
"""角色 API 测试。"""

from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image


def make_image_file(color: str = "red") -> bytes:
    """生成测试用头像图片。"""
    buffer = BytesIO()
    image = Image.new("RGB", (64, 64), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def create_project(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/v1/projects", data={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def create_character(
    client: AsyncClient,
    project_id: str,
    name: str,
    description: str = "",
    image: bytes | None = None,
) -> dict:
    files = None
    if image is not None:
        files = {"image": ("avatar.png", image, "image/png")}
    response = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        data={"name": name, "description": description},
        files=files,
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_create_character_with_image_returns_image_url(client: AsyncClient) -> None:
    project_id = await create_project(client, "角色测试项目")

    character = await create_character(
        client,
        project_id,
        "林夏",
        "主角描述",
        make_image_file(),
    )

    assert character["project_id"] == project_id
    assert character["name"] == "林夏"
    assert character["description"] == "主角描述"
    assert character["image_url"].startswith("/character-images/")
    assert character["is_favorited"] is False
    assert "created_at" in character
    assert "updated_at" in character


@pytest.mark.asyncio
async def test_create_character_generates_numbered_name_when_duplicate(client: AsyncClient) -> None:
    project_id = await create_project(client, "重名创建项目")
    await create_character(client, project_id, "未命名角色")

    duplicate = await create_character(client, project_id, "未命名角色")

    assert duplicate["name"] == "未命名角色 (2)"


@pytest.mark.asyncio
async def test_update_character_rejects_duplicate_name(client: AsyncClient) -> None:
    project_id = await create_project(client, "重名更新项目")
    first = await create_character(client, project_id, "林夏")
    second = await create_character(client, project_id, "顾明")

    response = await client.patch(
        f"/api/v1/characters/{second['id']}",
        data={"name": first["name"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "角色名称已存在"


@pytest.mark.asyncio
async def test_list_characters_is_scoped_by_project(client: AsyncClient) -> None:
    project_id = await create_project(client, "项目 A")
    other_project_id = await create_project(client, "项目 B")
    await create_character(client, project_id, "项目 A 角色")
    await create_character(client, other_project_id, "项目 B 角色")

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "项目 A 角色"
    assert data["items"][0]["project_id"] == project_id
    assert "token_count" in data["items"][0]
    assert "description" not in data["items"][0]


@pytest.mark.asyncio
async def test_list_characters_orders_by_updated_at_desc(client: AsyncClient) -> None:
    project_id = await create_project(client, "排序项目")
    first = await create_character(client, project_id, "先创建")
    second = await create_character(client, project_id, "后创建")

    update_response = await client.patch(
        f"/api/v1/characters/{first['id']}",
        data={"name": "最近编辑"},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["最近编辑", second["name"]]


@pytest.mark.asyncio
async def test_update_character_favorite_state(client: AsyncClient) -> None:
    project_id = await create_project(client, "收藏项目")
    character = await create_character(client, project_id, "可收藏角色")

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"is_favorited": "true"},
    )

    assert response.status_code == 200
    assert response.json()["is_favorited"] is True


@pytest.mark.asyncio
async def test_batch_favorite_characters_is_scoped_by_project(client: AsyncClient) -> None:
    project_id = await create_project(client, "批量收藏项目")
    other_project_id = await create_project(client, "其他批量收藏项目")
    first = await create_character(client, project_id, "角色一")
    second = await create_character(client, project_id, "角色二")
    external = await create_character(client, other_project_id, "外部角色")

    response = await client.post(
        f"/api/v1/projects/{project_id}/characters/batch/favorite",
        json={"character_ids": [first["id"], second["id"], external["id"]], "is_favorited": True},
    )

    assert response.status_code == 200
    assert response.json() == {"updated_count": 2}
    list_response = await client.get(f"/api/v1/projects/{project_id}/characters")
    assert list_response.status_code == 200
    assert {item["id"]: item["is_favorited"] for item in list_response.json()["items"]} == {
        first["id"]: True,
        second["id"]: True,
    }
    external_response = await client.get(f"/api/v1/characters/{external['id']}")
    assert external_response.status_code == 200
    assert external_response.json()["is_favorited"] is False


@pytest.mark.asyncio
async def test_batch_delete_characters_is_scoped_by_project(client: AsyncClient) -> None:
    project_id = await create_project(client, "批量删除项目")
    other_project_id = await create_project(client, "其他批量删除项目")
    first = await create_character(client, project_id, "删除一")
    second = await create_character(client, project_id, "删除二")
    external = await create_character(client, other_project_id, "外部删除角色")

    response = await client.post(
        f"/api/v1/projects/{project_id}/characters/batch/delete",
        json={"character_ids": [first["id"], second["id"], external["id"]]},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted_count": 2}
    list_response = await client.get(f"/api/v1/projects/{project_id}/characters")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []
    external_response = await client.get(f"/api/v1/characters/{external['id']}")
    assert external_response.status_code == 200


@pytest.mark.asyncio
async def test_list_characters_places_favorites_first_then_updated_desc(client: AsyncClient) -> None:
    project_id = await create_project(client, "收藏排序项目")
    favorite_old = await create_character(client, project_id, "收藏旧")
    normal_recent = await create_character(client, project_id, "普通新")
    favorite_recent = await create_character(client, project_id, "收藏新")

    old_favorite_response = await client.patch(
        f"/api/v1/characters/{favorite_old['id']}",
        data={"is_favorited": "true"},
    )
    assert old_favorite_response.status_code == 200
    recent_favorite_response = await client.patch(
        f"/api/v1/characters/{favorite_recent['id']}",
        data={"is_favorited": "true"},
    )
    assert recent_favorite_response.status_code == 200

    response = await client.get(f"/api/v1/projects/{project_id}/characters")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == [favorite_recent["name"], favorite_old["name"], normal_recent["name"]]


@pytest.mark.asyncio
async def test_search_characters_returns_name_and_description_matches(client: AsyncClient) -> None:
    project_id = await create_project(client, "搜索角色项目")
    other_project_id = await create_project(client, "其他搜索项目")
    first = await create_character(client, project_id, "林夏", "第一行\n喜欢银色匕首")
    await create_character(client, project_id, "顾银", "普通描述")
    await create_character(client, other_project_id, "银色外部角色", "不应出现在结果中")

    response = await client.get(
        f"/api/v1/projects/{project_id}/characters/search",
        params={"q": "银"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_characters"] == 2
    assert data["total_matches"] == 2
    results_by_name = {item["character_name"]: item for item in data["results"]}
    assert results_by_name["林夏"]["character_id"] == first["id"]
    assert results_by_name["林夏"]["matches"][0] == {
        "line_number": 2,
        "line_text": "喜欢银色匕首",
    }
    assert results_by_name["顾银"]["matches"][0] == {
        "line_number": 0,
        "line_text": "顾银",
    }


@pytest.mark.asyncio
async def test_update_character_refreshes_updated_at(client: AsyncClient) -> None:
    project_id = await create_project(client, "更新时间项目")
    character = await create_character(client, project_id, "原名称")

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"name": "新名称", "description": "新描述"},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "新名称"
    assert updated["description"] == "新描述"
    assert updated["updated_at"] > character["updated_at"]


@pytest.mark.asyncio
async def test_replace_character_image_deletes_old_file(
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import settings as app_settings

    monkeypatch.setattr(app_settings.settings, "character_images_dir", tmp_path)
    project_id = await create_project(client, "头像替换项目")
    character = await create_character(client, project_id, "有头像", image=make_image_file("red"))
    old_filename = character["image_url"].split("/character-images/", 1)[1].split("?", 1)[0]
    old_file = tmp_path / old_filename
    assert old_file.exists()

    response = await client.patch(
        f"/api/v1/characters/{character['id']}",
        data={"name": character["name"]},
        files={"image": ("avatar.png", make_image_file("blue"), "image/png")},
    )

    assert response.status_code == 200
    new_filename = response.json()["image_url"].split("/character-images/", 1)[1].split("?", 1)[0]
    assert new_filename != old_filename
    assert not old_file.exists()
    assert (tmp_path / new_filename).exists()


@pytest.mark.asyncio
async def test_delete_character_deletes_image_file(
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import settings as app_settings

    monkeypatch.setattr(app_settings.settings, "character_images_dir", tmp_path)
    project_id = await create_project(client, "头像删除项目")
    character = await create_character(client, project_id, "待删除", image=make_image_file())
    filename = character["image_url"].split("/character-images/", 1)[1].split("?", 1)[0]
    image_file = tmp_path / filename
    assert image_file.exists()

    response = await client.delete(f"/api/v1/characters/{character['id']}")

    assert response.status_code == 204
    assert not image_file.exists()


@pytest.mark.asyncio
async def test_missing_project_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/missing-project/characters")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_character_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/characters/missing-character")

    assert response.status_code == 404
