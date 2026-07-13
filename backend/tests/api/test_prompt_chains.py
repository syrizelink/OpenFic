# -*- coding: utf-8 -*-
"""Prompt chain API tests for agent-only defaults."""

from pathlib import Path

from httpx import AsyncClient


class TestPromptChainAPI:
    async def test_metadata_groups_flat_prompt_ids(
        self,
        client: AsyncClient,
        isolated_prompts_dir: Path,
    ) -> None:
        custom_yaml = isolated_prompts_dir / "assistant" / "agent" / "legacy-custom.yaml"
        custom_yaml.parent.mkdir(parents=True)
        custom_yaml.write_text("entries: []\n", encoding="utf-8")

        response = await client.get("/api/v1/prompt-chains/categories")

        assert response.status_code == 200
        categories = {category["id"]: category for category in response.json()["categories"]}

        assert set(categories) == {
            "session",
            "memory",
            "builtin-agents",
            "custom-agents",
        }
        assert {
            prompt["id"] for prompt in categories["session"]["prompts"]
        } == {"session-title", "session-compaction"}
        assert {
            prompt["id"] for prompt in categories["memory"]["prompts"]
        } == {"memory-chapter-summary", "memory-range-summary"}
        assert "builtin-agent--explorer" in {
            prompt["id"] for prompt in categories["builtin-agents"]["prompts"]
        }
        assert categories["custom-agents"]["prompts"] == []

    async def test_get_latest_agent_version_uses_default_yaml(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/prompt-chains/builtin-agent--explorer/versions/latest",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["version_number"] == 0
        assert data["version"]["prompt_id"] == "builtin-agent--explorer"
        assert len(data["entries"]) > 0
        assert all("finish_subagent" not in entry["content"] for entry in data["entries"])

    async def test_get_default_version_returns_yaml_after_creating_version(
        self,
        client: AsyncClient,
    ) -> None:
        prompt_id = "session-title"
        default_response = await client.get(
            f"/api/v1/prompt-chains/{prompt_id}/versions/default",
        )

        assert default_response.status_code == 200
        default_data = default_response.json()

        create_response = await client.post(
            f"/api/v1/prompt-chains/{prompt_id}/versions",
            json={
                "parent_version_id": "default",
                "entries": [
                    {
                        **entry,
                        "content": f"{entry['content']}\n自定义版本内容",
                    }
                    for entry in default_data["entries"]
                ],
            },
        )
        assert create_response.status_code == 201

        response = await client.get(
            f"/api/v1/prompt-chains/{prompt_id}/versions/default",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["id"] == "default"
        assert data["version"]["version_number"] == 0
        assert all("自定义版本内容" not in entry["content"] for entry in data["entries"])

    async def test_diff_version_against_default_yaml(self, client: AsyncClient) -> None:
        prompt_id = "session-title"
        default_response = await client.get(
            f"/api/v1/prompt-chains/{prompt_id}/versions/default",
        )
        assert default_response.status_code == 200
        default_data = default_response.json()

        create_response = await client.post(
            f"/api/v1/prompt-chains/{prompt_id}/versions",
            json={
                "parent_version_id": "default",
                "entries": [
                    {
                        **entry,
                        "content": f"{entry['content']}\n自定义版本内容",
                    }
                    for entry in default_data["entries"]
                ],
            },
        )
        assert create_response.status_code == 201
        version_id = create_response.json()["version"]["id"]

        response = await client.get(
            f"/api/v1/prompt-chains/{prompt_id}/versions/default/diff/{version_id}",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["base_version"]["id"] == "default"
        assert data["compare_version"]["id"] == version_id
        assert data["diffs"]

    async def test_list_versions_includes_default_version(self, client: AsyncClient) -> None:
        prompt_id = "session-title"
        latest_response = await client.get(
            f"/api/v1/prompt-chains/{prompt_id}/versions/latest",
        )
        assert latest_response.status_code == 200

        create_response = await client.post(
            f"/api/v1/prompt-chains/{prompt_id}/versions",
            json={
                "parent_version_id": "default",
                "entries": latest_response.json()["entries"],
            },
        )
        assert create_response.status_code == 201

        response = await client.get(f"/api/v1/prompt-chains/{prompt_id}/versions")

        assert response.status_code == 200
        assert [version["version_number"] for version in response.json()] == [1, 0]
        assert response.json()[-1]["id"] == "default"

    async def test_compile_agent_version_uses_default_yaml(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/prompt-chains/builtin-agent--explorer/compile",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tokens"] >= 0
        assert len(data["entries"]) > 0
        assert all(entry["name"] for entry in data["entries"])

    async def test_create_version_uses_flat_prompt_id(self, client: AsyncClient) -> None:
        latest_response = await client.get(
            "/api/v1/prompt-chains/session-title/versions/latest",
        )
        latest_data = latest_response.json()

        response = await client.post(
            "/api/v1/prompt-chains/session-title/versions",
            json={
                "parent_version_id": "default",
                "entries": latest_data["entries"],
            },
        )

        assert response.status_code == 201
        assert response.json()["version"]["prompt_id"] == "session-title"

    async def test_search_version_entries_returns_name_and_content_matches(
        self,
        client: AsyncClient,
    ) -> None:
        version_response = await client.post(
            "/api/v1/prompt-chains/session-title/versions",
            json={
                "parent_version_id": "default",
                "entries": [
                    {
                        "name": "系统规则",
                        "role": "system",
                        "content": "第一行\n包含关键字的内容",
                        "order_index": 0,
                        "is_enabled": True,
                        "token_count": 0,
                    },
                    {
                        "name": "关键字条目",
                        "role": "user",
                        "content": "普通内容",
                        "order_index": 1,
                        "is_enabled": True,
                        "token_count": 0,
                    },
                ],
            },
        )
        assert version_response.status_code == 201
        version_id = version_response.json()["version"]["id"]

        response = await client.get(
            f"/api/v1/prompt-chains/session-title/versions/{version_id}/search",
            params={"q": "关键字"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_entries"] == 2
        assert data["total_matches"] == 2
        results_by_name = {item["entry_name"]: item for item in data["results"]}
        assert results_by_name["系统规则"]["matches"] == [
            {
                "line_number": 2,
                "line_text": "包含关键字的内容",
            },
        ]
        assert results_by_name["关键字条目"]["matches"] == [
            {
                "line_number": 0,
                "line_text": "关键字条目",
            },
        ]
