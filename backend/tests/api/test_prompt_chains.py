# -*- coding: utf-8 -*-
"""Prompt chain API tests for agent-only defaults."""

from pathlib import Path

from httpx import AsyncClient


class TestPromptChainAPI:
    async def test_metadata_excludes_legacy_assistant_chat(
        self,
        client: AsyncClient,
        isolated_prompts_dir: Path,
    ) -> None:
        custom_yaml = isolated_prompts_dir / "assistant" / "agent" / "legacy-custom.yaml"
        custom_yaml.write_text("entries: []\n", encoding="utf-8")

        response = await client.get("/api/v1/prompt-chains/metadata")

        assert response.status_code == 200
        assistant = next(
            mode for mode in response.json()["modes"] if mode["value"] == "assistant"
        )
        task_names = {task["value"] for task in assistant["tasks"]}
        assert "chat" not in task_names
        assert "agent" in task_names
        agent_task = next(task for task in assistant["tasks"] if task["value"] == "agent")
        assert all(agent["value"] != "legacy-custom" for agent in agent_task["agents"])

    async def test_get_latest_agent_version_uses_default_yaml(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/prompt-chains/assistant/agent/versions/latest",
            params={"agent_name": "explorer"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["version_number"] == 0
        assert data["version"]["agent_name"] == "explorer"
        assert len(data["entries"]) > 0
        assert all("finish_subagent" not in entry["content"] for entry in data["entries"])

    async def test_compile_agent_version_uses_default_yaml(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/prompt-chains/assistant/agent/compile",
            params={"agent_name": "explorer"},
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tokens"] >= 0
        assert len(data["entries"]) > 0
