# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_update_and_list_agent_rules_with_title(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/agent-rules",
        json={
            "title": "回复语言",
            "content": "回复时使用简体中文",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == "回复语言"
    assert created["content"] == "回复时使用简体中文"

    rule_id = created["id"]
    update_response = await client.patch(
        f"/api/v1/agent-rules/{rule_id}",
        json={
            "title": "输出语言",
            "content": "始终使用简体中文回复",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "输出语言"
    assert updated["content"] == "始终使用简体中文回复"

    list_response = await client.get("/api/v1/agent-rules")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["title"] == "输出语言"
    assert payload["items"][0]["content"] == "始终使用简体中文回复"
