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
            json={"project_id": None, "chapter_id": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tokens"] >= 0
        assert len(data["entries"]) > 0

    async def test_compile_latest_chapter_uses_last_volume_last_chapter(
        self,
        client: AsyncClient,
        monkeypatch,
    ) -> None:
        from app.macro.compiler import CompileResult, CompiledEntry
        import app.macro.compiler as compiler_module

        compile_calls: list[dict] = []

        class FakeCompiler:
            def __init__(self, _session):
                pass

            async def compile(self, *, entries, project_id, chapter_id):
                compile_calls.append(
                    {
                        "project_id": project_id,
                        "chapter_id": chapter_id,
                    }
                )
                return CompileResult(
                    entries=[
                        CompiledEntry(
                            role="system",
                            content=f"chapter_id={chapter_id}",
                            token_count=1,
                        )
                    ],
                    total_tokens=1,
                )

        monkeypatch.setattr(compiler_module, "PromptChainCompiler", FakeCompiler)

        project_response = await client.post(
            "/api/v1/projects",
            data={"title": "测试小说"},
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]
        first_volume = (
            await client.get(f"/api/v1/projects/{project_id}/volumes")
        ).json()[0]
        second_volume_response = await client.post(
            f"/api/v1/projects/{project_id}/volumes",
            json={"title": "第二卷"},
        )
        assert second_volume_response.status_code == 201
        second_volume = second_volume_response.json()

        for index in range(3):
            response = await client.post(
                f"/api/v1/projects/{project_id}/chapters",
                json={"volume_id": first_volume["id"], "title": f"第一卷第{index + 1}章"},
            )
            assert response.status_code == 201
        last_chapter_id = None
        for index in range(2):
            response = await client.post(
                f"/api/v1/projects/{project_id}/chapters",
                json={"volume_id": second_volume["id"], "title": f"第二卷第{index + 1}章"},
            )
            assert response.status_code == 201
            last_chapter_id = response.json()["id"]

        response = await client.post(
            "/api/v1/prompt-chains/assistant/agent/compile",
            params={"agent_name": "explorer"},
            json={"project_id": project_id, "chapter_id": "latest"},
        )

        assert response.status_code == 200
        assert compile_calls == [{"project_id": project_id, "chapter_id": last_chapter_id}]
        assert response.json()["entries"][0]["content"] == f"chapter_id={last_chapter_id}"
