# -*- coding: utf-8 -*-
"""Agent Definitions API 测试。"""

from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_agent_definitions(client: AsyncClient):
    response = await client.get("/api/v1/agent-definitions")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "definitions" in data
    keys = {d["key"] for d in data["definitions"]}
    assert "explorer" in keys
    assert "writer" in keys
    primary = next(d for d in data["definitions"] if d["kind"] == "primary")
    assert "description" in primary
    assert primary["enabled_skill_ids"] == []


@pytest.mark.asyncio
async def test_get_agent_definition(client: AsyncClient):
    response = await client.get("/api/v1/agent-definitions/explorer")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["key"] == "explorer"
    assert data["source"] == "builtin"
    assert data["kind"] == "subagent"
    assert "description" in data


@pytest.mark.asyncio
async def test_list_agent_tool_categories(client: AsyncClient):
    response = await client.get("/api/v1/agent-definitions/tool-categories")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "categories" in data
    keys = {item["key"] for item in data["categories"]}
    assert "chapter_read" in keys
    assert "chapter_write" in keys

    chapter_read = next(item for item in data["categories"] if item["key"] == "chapter_read")
    assert chapter_read["tool_keys"] == [
        "list_volumes",
        "list_chapters",
        "read_chapter",
        "search_chapters",
        "update_index",
    ]


@pytest.mark.asyncio
async def test_get_nonexistent_agent_definition(client: AsyncClient):
    response = await client.get("/api/v1/agent-definitions/nonexistent")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_custom_agent_definition(
    client: AsyncClient,
    isolated_prompts_dir: Path,
):
    body = {
        "key": "custom-bot",
        "display_name": "Custom Bot",
        "description": "Custom description",
        "kind": "subagent",
        "prompt_agent_name": "custom-bot",
        "model_id": None,
        "tool_category_keys": ["chapter_read"],
        "enabled_skill_ids": ["skill-a", "skill-b"],
        "metadata": {},
        "delegatable_agents": ["explorer"],
    }
    response = await client.post("/api/v1/agent-definitions", json=body)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["key"] == "custom-bot"
    assert data["source"] == "custom"
    assert data["description"] == "Custom description"
    assert data["enabled_skill_ids"] == ["skill-a", "skill-b"]
    assert data["delegatable_agents"] == ["explorer"]

    assert not (isolated_prompts_dir / "assistant" / "agent" / "custom-bot.yaml").exists()
    assert not Path(
        "backend/app/prompts/assistant/agent/custom-bot.yaml"
    ).exists()

    latest_response = await client.get(
        "/api/v1/prompt-chains/assistant/agent/versions/latest",
        params={"agent_name": "custom-bot"},
    )
    assert latest_response.status_code == status.HTTP_200_OK
    latest_data = latest_response.json()
    assert latest_data["version"]["version_number"] == 1
    assert latest_data["version"]["agent_name"] == "custom-bot"
    assert len(latest_data["entries"]) > 0

    metadata_response = await client.get("/api/v1/prompt-chains/metadata")
    assert metadata_response.status_code == status.HTTP_200_OK
    assistant_mode = next(
        mode for mode in metadata_response.json()["modes"] if mode["value"] == "assistant"
    )
    agent_task = next(
        task for task in assistant_mode["tasks"] if task["value"] == "agent"
    )
    assert any(agent["value"] == "custom-bot" for agent in agent_task["agents"])


@pytest.mark.asyncio
async def test_create_duplicate_agent_definition(client: AsyncClient):
    body = {
        "key": "dup-bot",
        "display_name": "Duplicate Bot",
        "kind": "subagent",
        "prompt_agent_name": "dup-bot",
        "tool_category_keys": [],
        "enabled_skill_ids": [],
    }
    response = await client.post("/api/v1/agent-definitions", json=body)
    assert response.status_code == status.HTTP_201_CREATED

    response = await client.post("/api/v1/agent-definitions", json=body)
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_update_custom_agent_definition(client: AsyncClient):
    create_body = {
        "key": "edit-me",
        "display_name": "Edit Me",
        "description": "Before update",
        "kind": "subagent",
        "prompt_agent_name": "edit-me",
        "tool_category_keys": ["chapter_read"],
        "enabled_skill_ids": [],
    }
    await client.post("/api/v1/agent-definitions", json=create_body)

    update_body = {
        "display_name": "Edited Bot",
        "description": "After update",
        "enabled_skill_ids": ["skill-z"],
        "delegatable_agents": ["explorer", "writer"],
    }
    response = await client.put("/api/v1/agent-definitions/edit-me", json=update_body)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["display_name"] == "Edited Bot"
    assert data["description"] == "After update"
    assert data["enabled_skill_ids"] == ["skill-z"]
    assert data["delegatable_agents"] == ["explorer", "writer"]


@pytest.mark.asyncio
async def test_update_builtin_creates_override(client: AsyncClient):
    update_body = {"display_name": "Renamed Reviewer"}
    response = await client.put("/api/v1/agent-definitions/reviewer", json=update_body)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["display_name"] == "Renamed Reviewer"
    assert data["source"] == "builtin"
    assert data["key"] == "reviewer"


@pytest.mark.asyncio
async def test_reset_builtin_agent_definition(client: AsyncClient):
    update_body = {"display_name": "Custom Reviewer"}
    await client.put("/api/v1/agent-definitions/reviewer", json=update_body)

    response = await client.post("/api/v1/agent-definitions/reviewer/reset")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["key"] == "reviewer"
    assert data["source"] == "builtin"
    assert data["display_name"] == "Reviewer"


@pytest.mark.asyncio
async def test_reset_custom_agent_definition_rejected(client: AsyncClient):
    create_body = {
        "key": "custom-only",
        "display_name": "Custom Only",
        "kind": "subagent",
        "prompt_agent_name": "custom-only",
        "tool_category_keys": ["chapter_read"],
        "enabled_skill_ids": [],
    }
    await client.post("/api/v1/agent-definitions", json=create_body)

    response = await client.post("/api/v1/agent-definitions/custom-only/reset")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_delete_custom_agent_definition(client: AsyncClient):
    create_body = {
        "key": "del-me",
        "display_name": "Delete Me",
        "kind": "subagent",
        "prompt_agent_name": "del-me",
        "tool_category_keys": ["chapter_read"],
        "enabled_skill_ids": [],
    }
    await client.post("/api/v1/agent-definitions", json=create_body)

    response = await client.delete("/api/v1/agent-definitions/del-me")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = await client.get("/api/v1/agent-definitions/del-me")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_nonexistent_agent_definition(client: AsyncClient):
    response = await client.delete("/api/v1/agent-definitions/nonexistent")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_builtin_agent_definition_rejected(client: AsyncClient):
    response = await client.delete("/api/v1/agent-definitions/primary")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
