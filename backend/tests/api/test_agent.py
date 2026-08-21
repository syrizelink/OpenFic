# -*- coding: utf-8 -*-
"""Agent API 测试。"""

import asyncio
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import ANY

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.child_runs import (
    count_pending_child_run_requests,
    create_child_run,
    record_child_run_pending_approval,
)
from app.agent_runtime.persistence.model import AgentChildRunRequest
from app.agent_runtime.revisions import begin_user_revision
from app.agent_runtime.runner.checkpointer import get_checkpointer, reset_checkpointer
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.runner.session_runner import SessionRunner
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.api.routers.agent_runtime import (
    _SESSION_RUNNERS,
    _build_model_config,
    _launch_task,
)
from app.settings import settings
from app.socket.handlers import agent_session_room, agent_subagents_room
from app.storage.models.chapter import Chapter
from app.storage.models.commit import Commit
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from app.storage.repos import revision_repo
from app.storage.services import task_service

pytestmark = pytest.mark.usefixtures("fast_checkpoint_sqlite")


@pytest_asyncio.fixture(autouse=True)
async def reset_agent_runtime_globals(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(tmp_path / "checkpoints.db"))
    await get_agent_run_registry().cancel_all()
    _SESSION_RUNNERS.clear()
    await reset_checkpointer()
    try:
        yield
    finally:
        await get_agent_run_registry().cancel_all()
        _SESSION_RUNNERS.clear()
        await reset_checkpointer()


async def _seed_agent_target(client: AsyncClient) -> dict[str, str]:
    project_response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说", "description": "一个关于冒险的故事"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    volumes_response = await client.get(f"/api/v1/projects/{project_id}/volumes")
    assert volumes_response.status_code == 200
    volume_id = volumes_response.json()[0]["id"]

    chapter_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={
            "volume_id": volume_id,
            "title": "第一章 开始",
            "content": "这是一个晴朗的早晨，主人公踏上了旅程。",
        },
    )
    assert chapter_response.status_code == 201
    chapter_id = chapter_response.json()["id"]

    provider_response = await client.post(
        "/api/v1/model-providers",
        data={
            "name": "测试提供商",
            "url": "https://api.test.com",
            "api_key": "test_api_key",
            "provider_type": "openai-compatible",
        },
    )
    assert provider_response.status_code == 201
    provider_id = provider_response.json()["id"]

    model_response = await client.post(
        "/api/v1/models",
        json={
            "name": "测试模型",
            "provider_id": provider_id,
            "model_id": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 2000,
            "context_length": 8000,
        },
    )
    assert model_response.status_code == 201
    model_id = model_response.json()["id"]

    return {
        "project_id": project_id,
        "chapter_id": chapter_id,
        "provider_id": provider_id,
        "model_id": model_id,
    }


def _image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 3), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
class TestAgentAPI:
    async def test_upload_agent_image_attachment_returns_session_owned_metadata(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        session_id = session_response.json()["session_id"]
        monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path / "agent-attachments", raising=False)

        response = await client.post(
            f"/api/v1/agent/sessions/{session_id}/attachments",
            files={"image": ("reference.png", _image_bytes(), "image/png")},
        )

        assert response.status_code == status.HTTP_201_CREATED
        attachment = response.json()
        assert attachment["id"]
        assert attachment["session_id"] == session_id
        assert attachment["file_name"] == "reference.png"
        assert attachment["mime_type"] == "image/png"
        assert attachment["width"] == 2
        assert attachment["height"] == 3
        assert attachment["url"].startswith("/agent-attachments/")
        assert settings.agent_attachments_dir.joinpath(attachment["storage_name"]).is_file()

    async def test_send_agent_message_passes_session_attachment_metadata_to_runner(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        session_id = session_response.json()["session_id"]
        monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path / "agent-attachments")
        attachment_response = await client.post(
            f"/api/v1/agent/sessions/{session_id}/attachments",
            files={"image": ("reference.png", _image_bytes(), "image/png")},
        )
        attachment = attachment_response.json()
        runner = _SESSION_RUNNERS[session_id]
        runner.run = MagicMock(return_value=object())

        with patch("app.api.routers.agent_runtime._launch_task", AsyncMock()):
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "请描述", "attachments": [attachment["id"]]},
            )

        assert response.status_code == status.HTTP_200_OK
        runner.run.assert_called_once_with(
            user_request="请描述",
            attachments=[
                {
                    "id": attachment["id"],
                    "storage_name": attachment["storage_name"],
                    "file_name": "reference.png",
                    "mime_type": "image/png",
                    "size_bytes": attachment["size_bytes"],
                    "width": 2,
                    "height": 3,
                    "url": attachment["url"],
                }
            ],
        )

    async def test_build_model_config_allows_reasoning_effort_for_uncataloged_model(self) -> None:
        model = SimpleNamespace(
            id="uncataloged-model-record",
            model_id="new-reasoning-model",
            context_length=128000,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            min_p=0.0,
            top_a=0.0,
            max_tokens=None,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            repetition_penalty=1.0,
        )
        provider = SimpleNamespace(
            provider_type="anthropic",
            url="https://api.anthropic.com",
        )

        config = await _build_model_config(model, provider, "sk-test", "high")

        assert config["reasoning_effort"] == "high"

    async def test_build_model_config_omits_disabled_reasoning_effort(self) -> None:
        model = SimpleNamespace(
            id="reasoning-model-record",
            model_id="reasoning-model",
            context_length=128000,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            min_p=0.0,
            top_a=0.0,
            max_tokens=None,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            repetition_penalty=1.0,
        )
        provider = SimpleNamespace(
            provider_type="openai-compatible",
            url="https://custom.api/v1",
        )

        config = await _build_model_config(model, provider, "sk-test", "off")

        assert "reasoning_effort" not in config

    async def test_list_agent_tools_success(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/agent/tools")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "key": "ask_user",
                "is_readonly": True,
            },
            {
                "key": "write_plan",
                "is_readonly": False,
            },
            {
                "key": "dispatch_subagent",
                "is_readonly": True,
            },
            {
                "key": "notify_subagent",
                "is_readonly": True,
            },
            {
                "key": "recycle_subagent",
                "is_readonly": True,
            },
            {
                "key": "list_volumes",
                "is_readonly": True,
            },
            {
                "key": "list_chapters",
                "is_readonly": True,
            },
            {
                "key": "read_chapter",
                "is_readonly": True,
            },
            {
                "key": "search_chapters",
                "is_readonly": True,
            },
            {
                "key": "update_index",
                "is_readonly": False,
            },
            {
                "key": "read_chapter_summaries",
                "is_readonly": True,
            },
            {
                "key": "read_range_summaries",
                "is_readonly": True,
            },
            {
                "key": "write_chapter",
                "is_readonly": False,
            },
            {
                "key": "edit_chapter",
                "is_readonly": False,
            },
            {
                "key": "delete_chapter",
                "is_readonly": False,
            },
            {
                "key": "create_volume",
                "is_readonly": False,
            },
            {
                "key": "edit_volume",
                "is_readonly": False,
            },
            {
                "key": "delete_volume",
                "is_readonly": False,
            },
            {
                "key": "move_chapter_to_volume",
                "is_readonly": False,
            },
            {
                "key": "list_notes",
                "is_readonly": True,
            },
            {
                "key": "read_note",
                "is_readonly": True,
            },
            {
                "key": "write_note",
                "is_readonly": False,
            },
            {
                "key": "edit_note",
                "is_readonly": False,
            },
            {
                "key": "delete_note",
                "is_readonly": False,
            },
            {
                "key": "move_note",
                "is_readonly": False,
            },
            {
                "key": "create_note_category",
                "is_readonly": False,
            },
            {
                "key": "edit_note_category",
                "is_readonly": False,
            },
            {
                "key": "delete_note_category",
                "is_readonly": False,
            },
            {
                "key": "list_characters",
                "is_readonly": True,
            },
            {
                "key": "read_character",
                "is_readonly": True,
            },
            {
                "key": "create_character",
                "is_readonly": False,
            },
            {
                "key": "edit_character",
                "is_readonly": False,
            },
            {
                "key": "delete_character",
                "is_readonly": False,
            },
            {
                "key": "list_world_entries",
                "is_readonly": True,
            },
            {
                "key": "read_world_entry",
                "is_readonly": True,
            },
            {
                "key": "create_world_entry",
                "is_readonly": False,
            },
            {
                "key": "edit_world_entry",
                "is_readonly": False,
            },
            {
                "key": "delete_world_entry",
                "is_readonly": False,
            },
            {
                "key": "activate_skill",
                "is_readonly": True,
            },
            {
                "key": "reference_skill",
                "is_readonly": True,
            },
        ]

    async def test_create_agent_session_success(self, client: AsyncClient, session) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == target["project_id"]
        assert "mode" not in data
        assert data["status"] == "created"
        assert data["task_id"]
        assert data["session_id"].startswith("agent_")
        assert "checkpoint_id" not in data
        assert data["task_title"]
        assert data["session_id"] in _SESSION_RUNNERS

        created_task = await task_service.get_task(session, data["task_id"])
        assert created_task.title == data["task_title"]

    async def test_send_agent_message_uses_requested_model_for_next_run(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session.add(
            Task(
                id="task-model-switch",
                project_id=target["project_id"],
                title="模型切换",
                mode="agent",
                agent_session_id="session-model-switch",
            )
        )
        await session.commit()

        runner = SessionRunner(
            session_id="session-model-switch",
            task_id="task-model-switch",
            model_config={"max_context_tokens": 8000, "model_id": "previous-model"},
            project_id=target["project_id"],
        )
        runner.run = MagicMock(return_value=object())
        _SESSION_RUNNERS["session-model-switch"] = runner

        next_model_config = {"max_context_tokens": 32000, "model_id": "next-model"}
        with patch(
            "app.api.routers.agent_runtime._resolve_model_config",
            AsyncMock(return_value=next_model_config),
        ) as resolve_model_config, patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/session-model-switch/message",
                json={"message": "使用新模型继续", "model_id": "next-model-record"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["model_updated"] is True
        resolve_model_config.assert_awaited_once_with(session, "next-model-record", None)
        assert runner.model_config == next_model_config
        runner.run.assert_called_once_with(user_request="使用新模型继续")

    async def test_send_agent_message_uses_requested_primary_agent_for_next_run(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        definition_response = await client.post(
            "/api/v1/agent-definitions",
            json={
                "key": "custom-primary",
                "display_name": "Custom Primary",
                "kind": "primary",
                "prompt_agent_name": "custom-primary",
                "enabled_tool_categories": ["orchestration", "interaction", "chapter_read"],
                "enabled_skills": [],
                "metadata": {},
            },
        )
        assert definition_response.status_code == status.HTTP_201_CREATED
        session.add(
            Task(
                id="task-agent-switch",
                project_id=target["project_id"],
                title="主智能体切换",
                mode="agent",
                agent_session_id="session-agent-switch",
            )
        )
        await session.commit()

        runner = SessionRunner(
            session_id="session-agent-switch",
            task_id="task-agent-switch",
            model_config={"max_context_tokens": 8000, "model_id": "test-model"},
            project_id=target["project_id"],
            agent_key="build",
        )
        runner.run = MagicMock(return_value=object())
        _SESSION_RUNNERS["session-agent-switch"] = runner

        with patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/session-agent-switch/message",
                json={"message": "切换主智能体继续", "agent_key": "custom-primary"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert runner.agent_key == "custom-primary"
        runner.run.assert_called_once_with(user_request="切换主智能体继续")

    async def test_send_agent_message_falls_back_after_persisted_primary_agent_deleted(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        definition_response = await client.post(
            "/api/v1/agent-definitions",
            json={
                "key": "custom-primary",
                "display_name": "Custom Primary",
                "kind": "primary",
                "prompt_agent_name": "custom-primary",
                "enabled_tool_categories": ["orchestration", "interaction", "chapter_read"],
                "enabled_skills": [],
                "metadata": {},
            },
        )
        assert definition_response.status_code == status.HTTP_201_CREATED
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "agent_key": "custom-primary",
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        delete_response = await client.delete("/api/v1/agent-definitions/custom-primary")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        _SESSION_RUNNERS.clear()

        with patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(side_effect=lambda **kwargs: kwargs["coro"].close()),
        ):
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "继续旧会话"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert _SESSION_RUNNERS[session_id].agent_key == "build"

    async def test_send_agent_message_rejects_deleted_primary_agent(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session.add(
            Task(
                id="task-deleted-agent",
                project_id=target["project_id"],
                title="已删除主智能体",
                mode="agent",
                agent_session_id="session-deleted-agent",
            )
        )
        await session.commit()
        runner = SessionRunner(
            session_id="session-deleted-agent",
            task_id="task-deleted-agent",
            model_config={"max_context_tokens": 8000, "model_id": "test-model"},
            project_id=target["project_id"],
        )
        _SESSION_RUNNERS["session-deleted-agent"] = runner

        response = await client.post(
            "/api/v1/agent/sessions/session-deleted-agent/message",
            json={"message": "使用已删除主智能体", "agent_key": "deleted-primary"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "主智能体不存在: deleted-primary"

    async def test_send_agent_message_uses_new_model_after_deleted_model_session_rehydration(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        assert session_response.status_code == status.HTTP_200_OK
        session_id = session_response.json()["session_id"]

        new_model_response = await client.post(
            "/api/v1/models",
            json={
                "name": "新测试模型",
                "provider_id": target["provider_id"],
                "model_id": "gpt-4.1-mini",
                "temperature": 0.7,
                "max_tokens": 2000,
                "context_length": 32000,
            },
        )
        assert new_model_response.status_code == status.HTTP_201_CREATED
        new_model_id = new_model_response.json()["id"]

        delete_response = await client.delete(f"/api/v1/models/{target['model_id']}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        _SESSION_RUNNERS.clear()

        with patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(side_effect=lambda **kwargs: kwargs["coro"].close()),
        ):
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "使用新模型继续", "model_id": new_model_id},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["model_updated"] is True
        assert _SESSION_RUNNERS[session_id].model_config["model_record_id"] == new_model_id

    async def test_send_agent_message_updates_reasoning_effort_for_current_model(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session.add(
            Task(
                id="task-reasoning-effort",
                project_id=target["project_id"],
                title="推理强度",
                mode="agent",
                agent_session_id="session-reasoning-effort",
            )
        )
        await session.commit()

        runner = SessionRunner(
            session_id="session-reasoning-effort",
            task_id="task-reasoning-effort",
            model_config={
                "max_context_tokens": 8000,
                "model_id": "reasoning-model",
                "model_record_id": target["model_id"],
            },
            project_id=target["project_id"],
        )
        runner.run = MagicMock(return_value=object())
        _SESSION_RUNNERS["session-reasoning-effort"] = runner

        resolved_config = {
            "max_context_tokens": 8000,
            "model_id": "reasoning-model",
            "reasoning_effort": "high",
        }
        with patch(
            "app.api.routers.agent_runtime._resolve_model_config",
            AsyncMock(return_value=resolved_config),
        ) as resolve_model_config, patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/session-reasoning-effort/message",
                json={"message": "提高推理强度", "reasoning_effort": "high"},
            )

        assert response.status_code == status.HTTP_200_OK
        resolve_model_config.assert_awaited_once_with(session, target["model_id"], "high")
        assert runner.model_config == resolved_config

    async def test_send_agent_message_allows_reasoning_effort_for_uncataloged_model(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session.add(
            Task(
                id="task-uncataloged-reasoning-effort",
                project_id=target["project_id"],
                title="目录外推理强度",
                mode="agent",
                agent_session_id="session-uncataloged-reasoning-effort",
            )
        )
        await session.commit()

        runner = SessionRunner(
            session_id="session-uncataloged-reasoning-effort",
            task_id="task-uncataloged-reasoning-effort",
            model_config={
                "max_context_tokens": 8000,
                "model_id": "uncataloged-model",
                "model_record_id": target["model_id"],
            },
            project_id=target["project_id"],
        )
        runner.run = MagicMock(return_value=object())
        _SESSION_RUNNERS["session-uncataloged-reasoning-effort"] = runner

        resolved_config = {
            "max_context_tokens": 8000,
            "model_id": "uncataloged-model",
            "reasoning_effort": "high",
        }
        with patch(
            "app.api.routers.agent_runtime._resolve_model_config",
            AsyncMock(return_value=resolved_config),
        ) as resolve_model_config, patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/session-uncataloged-reasoning-effort/message",
                json={"message": "使用新模型推理", "reasoning_effort": "high"},
            )

        assert response.status_code == status.HTTP_200_OK
        resolve_model_config.assert_awaited_once_with(session, target["model_id"], "high")
        assert runner.model_config == resolved_config

    async def test_send_agent_message_updates_model_for_paused_session(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session.add(
            Task(
                id="task-model-resume",
                project_id=target["project_id"],
                title="模型恢复",
                mode="agent",
                agent_session_id="session-model-resume",
            )
        )
        await session.commit()

        original_model_config = {"max_context_tokens": 8000, "model_id": "original-model"}
        runner = SessionRunner(
            session_id="session-model-resume",
            task_id="task-model-resume",
            model_config=original_model_config,
            project_id=target["project_id"],
        )
        runner.run = MagicMock(return_value=object())
        _SESSION_RUNNERS["session-model-resume"] = runner

        next_model_config = {"max_context_tokens": 32000, "model_id": "new-model"}
        with patch(
            "app.api.routers.agent_runtime._resolve_model_config",
            AsyncMock(return_value=next_model_config),
        ) as resolve_model_config, patch(
            "app.api.routers.agent_runtime._launch_task",
            AsyncMock(),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/session-model-resume/message",
                json={"message": "继续原任务", "model_id": "new-model-record"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["model_updated"] is True
        resolve_model_config.assert_awaited_once_with(session, "new-model-record", None)
        assert runner.model_config == next_model_config
        runner.run.assert_called_once_with(user_request="继续原任务")

    async def test_send_agent_message_queues_without_updating_model(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session.add(
            Task(
                id="task-model-pending",
                project_id=target["project_id"],
                title="模型排队",
                mode="agent",
                agent_session_id="session-model-pending",
            )
        )
        await session.commit()

        runner = MagicMock()
        runner.task_id = "task-model-pending"
        runner.project_id = target["project_id"]
        runner.queue_pending_user_message = AsyncMock(
            return_value={
                "message_id": "pending-model-message",
                "content": "排队消息",
                "created_at": "2026-07-12T00:00:00+00:00",
            }
        )
        _SESSION_RUNNERS["session-model-pending"] = runner

        with patch(
            "app.api.routers.agent_runtime._resolve_model_config",
            AsyncMock(),
        ) as resolve_model_config, patch(
            "app.api.routers.agent_runtime.get_agent_run_registry"
        ) as get_registry:
            get_registry.return_value.is_running = AsyncMock(return_value=True)
            get_registry.return_value.is_cancelled = AsyncMock(return_value=False)
            response = await client.post(
                "/api/v1/agent/sessions/session-model-pending/message",
                json={"message": "排队消息", "model_id": "next-model-record"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["model_updated"] is False
        resolve_model_config.assert_not_awaited()
        runner.queue_pending_user_message.assert_awaited_once_with("排队消息")

    async def test_create_agent_session_rejects_mode_field(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "mode": "yolo",
                "max_iterations": 5,
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_agent_session_accepts_max_iterations_1000(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 1000,
            },
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_create_agent_session_rejects_max_iterations_above_1000(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 1001,
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_agent_session_succeeds_without_chapter_id(self, client: AsyncClient) -> None:
        provider_response = await client.post(
            "/api/v1/model-providers",
            data={
                "name": "测试提供商",
                "url": "https://api.test.com",
                "api_key": "test_api_key",
                "provider_type": "openai-compatible",
            },
        )
        provider_id = provider_response.json()["id"]

        model_response = await client.post(
            "/api/v1/models",
            json={
                "name": "测试模型",
                "provider_id": provider_id,
                "model_id": "gpt-3.5-turbo",
                "context_length": 8000,
            },
        )
        model_id = model_response.json()["id"]

        project_response = await client.post(
            "/api/v1/projects",
            data={"title": "测试小说"},
        )
        project_id = project_response.json()["id"]

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": project_id,
                "model_id": model_id,
                "max_iterations": 5,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"].startswith("agent_")
        assert data["status"] == "created"

    async def test_create_agent_session_with_agent_key(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
                "agent_key": "build",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent_key"] == "build"
        assert data["status"] == "created"

    async def test_create_agent_session_with_default_agent_key(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent_key"] == "build"

    async def test_create_agent_session_rejects_non_primary_agent_key(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
                "agent_key": "writer",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "primary" in response.json()["detail"]

    async def test_create_agent_session_rejects_disabled_primary(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        resp = await client.post(
            "/api/v1/agent-definitions",
            json={
                "key": "build",
                "display_name": "Build",
                "kind": "primary",
                "prompt_agent_name": "build",
                "enabled_tool_categories": ["orchestration", "interaction", "chapter_read"],
                "enabled_skills": [],
                "metadata": {},
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED

        resp = await client.put(
            "/api/v1/agent-definitions/build",
            json={"enabled": False},
        )
        assert resp.status_code == status.HTTP_200_OK

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
                "agent_key": "build",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "禁用" in response.json()["detail"]

    async def test_create_agent_session_with_custom_primary(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)

        response = await client.post(
            "/api/v1/agent-definitions",
            json={
                "key": "custom-primary",
                "display_name": "Custom Primary",
                "kind": "primary",
                "prompt_agent_name": "custom-primary",
                "enabled_tool_categories": ["orchestration", "interaction", "chapter_read"],
                "enabled_skills": [],
                "metadata": {},
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
                "agent_key": "custom-primary",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent_key"] == "custom-primary"
        assert data["status"] == "created"

    async def test_send_message_launches_background_run(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        with patch("app.api.routers.agent_runtime.SessionRunner.run", new=AsyncMock(return_value=None)) as mock_run:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "帮我写一个场景"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True
            await asyncio.sleep(0.05)
            mock_run.assert_awaited_once_with(user_request="帮我写一个场景")

    async def test_send_message_enqueues_title_job_for_new_default_title(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        with patch(
            "app.api.routers.agent_runtime.enqueue_session_title_job",
            new=AsyncMock(),
        ) as enqueue_mock, patch(
            "app.api.routers.agent_runtime.background_service.commit_and_notify",
            new=AsyncMock(),
        ) as commit_and_notify_mock, patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "帮我写一个场景"},
            )

        assert response.status_code == status.HTTP_200_OK
        enqueue_mock.assert_awaited_once()
        commit_and_notify_mock.assert_awaited_once()

    async def test_send_message_persists_running_state_and_emits_status_updates(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        task_id = session_response.json()["task_id"]
        run_gate = asyncio.Event()
        run_finished = asyncio.Event()

        async def fake_run(*, user_request: str) -> None:
            assert user_request == "帮我写一个场景"
            try:
                await run_gate.wait()
            finally:
                run_finished.set()

        with patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(side_effect=fake_run),
        ), patch(
            "app.api.routers.agent_runtime.emit",
            new=AsyncMock(),
        ) as emit_mock:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "帮我写一个场景"},
            )

            assert response.status_code == status.HTTP_200_OK
            await asyncio.sleep(0.05)

            running_task = await task_service.get_task(session, task_id)
            await session.refresh(running_task)
            assert running_task.is_running is True

            run_gate.set()
            await run_finished.wait()
            await asyncio.sleep(0.05)

            stopped_task = await task_service.get_task(session, task_id)
            await session.refresh(stopped_task)
            assert stopped_task.is_running is False

        status_payloads = [
            call.args[1]
            for call in emit_mock.await_args_list
            if call.args and call.args[0] == "background:event"
        ]
        lock_payloads = [
            call.args[1]
            for call in emit_mock.await_args_list
            if call.args and call.args[0] == "agent:settings_lock_changed"
        ]
        assert any(
            payload.get("type") == "task_run_status_updated"
            and payload.get("task_id") == task_id
            and payload.get("is_running") is True
            for payload in status_payloads
        )
        assert any(
            payload.get("type") == "task_run_status_updated"
            and payload.get("task_id") == task_id
            and payload.get("is_running") is False
            for payload in status_payloads
        )
        assert any(
            payload.get("session_id") == session_id and payload.get("is_running") is True
            for payload in lock_payloads
        )
        assert any(
            payload.get("session_id") == session_id and payload.get("is_running") is False
            for payload in lock_payloads
        )

    async def test_get_session_state_reports_active_background_run(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        fake_registry = SimpleNamespace(
            is_running=AsyncMock(return_value=True),
            is_cancelled=AsyncMock(return_value=False),
        )

        with patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ):
            response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == session_id
        assert data["state"]["session_id"] == session_id
        assert data["is_running"] is True
        fake_registry.is_running.assert_awaited_once_with(session_id)

    async def test_get_session_state_returns_pending_interrupts(
        self,
        client: AsyncClient,
    ) -> None:
        interrupt = SimpleNamespace(
            id="interrupt-approval-1",
            value={
                "type": "tool_approval",
                "tool_name": "edit_note",
                "args": {"note_id": "note-1"},
            },
        )
        fake_checkpointer = SimpleNamespace(
            aget_tuple=AsyncMock(
                return_value=SimpleNamespace(
                    checkpoint={"channel_values": {"session_id": "session-interrupt"}},
                    pending_writes=[("task-1", "__interrupt__", [interrupt])],
                )
            )
        )
        fake_registry = SimpleNamespace(is_running=AsyncMock(return_value=False))

        with patch(
            "app.api.routers.agent_runtime.get_checkpointer",
            new=AsyncMock(return_value=fake_checkpointer),
        ), patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ):
            response = await client.get("/api/v1/agent/sessions/session-interrupt")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["interrupts"] == [
            {
                "type": "tool_approval",
                "tool_name": "edit_note",
                "args": {"note_id": "note-1"},
                "interrupt_id": "interrupt-approval-1",
                "approval_id": "interrupt-approval-1",
                "id": "interrupt-approval-1",
            }
        ]

    async def test_get_session_state_hides_interrupts_after_session_cancelled(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="cancelled approval",
            agent_session_id=session_id,
            revision_type="agent",
            status="cancelled",
            is_checkpoint=True,
            project_snapshot_title="Cancelled approval",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        interrupt = SimpleNamespace(
            id="interrupt-approval-cancelled",
            value={"type": "tool_approval", "tool_name": "edit_note", "args": {}},
        )
        fake_checkpointer = SimpleNamespace(
            aget_tuple=AsyncMock(
                return_value=SimpleNamespace(
                    checkpoint={"channel_values": {"session_id": session_id}},
                    pending_writes=[("task-1", "__interrupt__", [interrupt])],
                )
            )
        )
        fake_registry = SimpleNamespace(is_running=AsyncMock(return_value=False))

        with patch(
            "app.api.routers.agent_runtime.get_checkpointer",
            new=AsyncMock(return_value=fake_checkpointer),
        ), patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ):
            response = await client.get(f"/api/v1/agent/sessions/{session_id}")

            task.is_running = True
            session.add(task)
            await session.commit()
            fake_registry.is_running.return_value = True
            running_response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_running"] is False
        assert response.json()["interrupts"] == []

        assert running_response.status_code == status.HTTP_200_OK
        assert running_response.json()["is_running"] is True
        assert running_response.json()["interrupts"] == []
        assert fake_registry.is_running.await_count == 2

    async def test_tool_approval_does_not_resume_cancelled_session(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="cancelled approval",
            agent_session_id=session_id,
            revision_type="agent",
            status="cancelled",
            is_checkpoint=True,
            project_snapshot_title="Cancelled approval",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        with patch("app.api.routers.agent_runtime._launch_task", new=AsyncMock()) as launch_task:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/tool-approval",
                json={"approval_id": "interrupt-approval-cancelled", "approved": False},
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"]["code"] == "session_cancelled"
        launch_task.assert_not_awaited()

    async def test_manual_compaction_does_not_resume_cancelled_session(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="cancelled compaction",
            agent_session_id=session_id,
            revision_type="agent",
            status="cancelled",
            is_checkpoint=True,
            project_snapshot_title="Cancelled compaction",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        task.is_running = False
        session.add(task)
        await session.commit()

        runner = _SESSION_RUNNERS[session_id]
        with patch.object(runner, "compact", new=AsyncMock()) as compact:
            response = await client.post(f"/api/v1/agent/sessions/{session_id}/compaction")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"]["code"] == "session_cancelled"
        compact.assert_not_awaited()

    async def test_resume_claims_interrupted_revision_once(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="waiting for approval",
            agent_session_id=session_id,
            revision_type="agent",
            status="interrupted",
            is_checkpoint=True,
            project_snapshot_title="Waiting approval",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        with patch("app.api.routers.agent_runtime._launch_task", new=AsyncMock()) as launch_task:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/tool-approval",
                json={"approval_id": "approval-claim", "approved": True},
            )
            duplicate_response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/tool-approval",
                json={"approval_id": "approval-claim", "approved": True},
            )

        await session.refresh(revision)
        assert response.status_code == status.HTTP_200_OK
        assert duplicate_response.status_code == status.HTTP_409_CONFLICT
        assert duplicate_response.json()["detail"]["code"] == "session_not_resumable"
        assert revision.status == "active"
        launch_task.assert_awaited_once()
        launch_task.await_args.kwargs["coro"].close()

    async def test_resume_claim_holds_session_lock_before_new_message_can_start(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="waiting for approval",
            agent_session_id=session_id,
            revision_type="agent",
            status="interrupted",
            is_checkpoint=True,
            project_snapshot_title="Waiting approval",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        claim_entered = asyncio.Event()
        release_claim = asyncio.Event()

        async def blocked_claim(*args: Any, **kwargs: Any) -> tuple[str, bool]:
            claim_entered.set()
            await release_claim.wait()
            return revision.id, True

        with patch(
            "app.api.routers.agent_runtime._claim_agent_session_resume",
            new=blocked_claim,
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.resume",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.api.routers.agent_runtime.emit",
            new=AsyncMock(),
        ):
            resume_task = asyncio.create_task(
                client.post(
                    f"/api/v1/agent/sessions/{session_id}/tool-approval",
                    json={"approval_id": "approval-lock-race", "approved": True},
                )
            )
            await asyncio.wait_for(claim_entered.wait(), timeout=1)

            message_task = asyncio.create_task(
                client.post(
                    f"/api/v1/agent/sessions/{session_id}/message",
                    json={"message": "new message during resume"},
                )
            )
            await asyncio.sleep(0.05)
            assert not message_task.done()

            release_claim.set()
            resume_response = await resume_task
            message_response = await message_task

        assert resume_response.status_code == status.HTTP_200_OK
        assert message_response.status_code == status.HTTP_200_OK

    async def test_resume_launch_failure_releases_interrupted_revision_claim(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="waiting for approval",
            agent_session_id=session_id,
            revision_type="agent",
            status="interrupted",
            is_checkpoint=True,
            project_snapshot_title="Waiting approval",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        async def fail_launch(**kwargs: Any) -> None:
            kwargs["coro"].close()
            raise RuntimeError("launch failed")

        with patch("app.api.routers.agent_runtime._launch_task", new=fail_launch):
            with pytest.raises(RuntimeError, match="launch failed"):
                await client.post(
                    f"/api/v1/agent/sessions/{session_id}/tool-approval",
                    json={"approval_id": "approval-claim", "approved": True},
                )

        await session.refresh(revision)
        assert revision.status == "interrupted"

    async def test_runner_finalizer_does_not_overwrite_cancelled_revision(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="cancelled revision",
            agent_session_id=payload["session_id"],
            revision_type="agent",
            status="cancelled",
            is_checkpoint=True,
            project_snapshot_title="Cancelled revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()

        finalized = await revision_repo.update_status_unless_cancelled(
            session,
            revision.id,
            "completed",
        )
        await session.commit()
        await session.refresh(revision)

        assert finalized is False
        assert revision.status == "cancelled"

    async def test_cancellation_does_not_overwrite_terminal_revision(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="completed revision",
            agent_session_id=payload["session_id"],
            revision_type="agent",
            status="completed",
            is_checkpoint=True,
            project_snapshot_title="Completed revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()

        cancelled = await revision_repo.cancel_active_or_interrupted_revision(
            session, revision.id
        )

        await session.commit()
        await session.refresh(revision)
        assert cancelled is False
        assert revision.status == "completed"

    async def test_startup_recovery_returns_orphaned_active_revision_to_interrupt(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="orphaned active revision",
            agent_session_id=payload["session_id"],
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Orphaned revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()

        recovered = await revision_repo.recover_active_revisions_for_stopped_tasks(session)
        await session.commit()
        await session.refresh(revision)

        assert recovered == 1
        assert revision.status == "interrupted"

    async def test_send_message_keeps_task_running_when_async_child_is_still_running(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        from app.agent_runtime.runner.run_registry import get_agent_run_registry

        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        task_id = session_response.json()["task_id"]
        run_gate = asyncio.Event()
        run_finished = asyncio.Event()
        child_gate = asyncio.Event()
        child_finished = asyncio.Event()

        async def fake_run(*, user_request: str) -> None:
            assert user_request == "帮我写一个场景"
            try:
                await run_gate.wait()
            finally:
                run_finished.set()

        async def fake_child() -> None:
            try:
                await child_gate.wait()
            finally:
                child_finished.set()

        with patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(side_effect=fake_run),
        ), patch(
            "app.api.routers.agent_runtime.emit",
            new=AsyncMock(),
        ):
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "帮我写一个场景"},
            )

            assert response.status_code == status.HTTP_200_OK
            await asyncio.sleep(0.05)

            row = await create_child_run(
                session,
                parent_session_id=session_id,
                parent_task_id=task_id,
                parent_thread_id=session_id,
                child_thread_id=f"{session_id}:child:running",
                agent_key="writer",
                dispatch_id="dispatch-running",
                tool_call_id="tool-call-running",
                request={"task": "write", "input": {}, "metadata": {}},
                status="running",
            )
            child_task = asyncio.create_task(fake_child())
            await get_agent_run_registry().register_child(session_id, row.id, child_task)

            run_gate.set()
            await run_finished.wait()
            await asyncio.sleep(0.05)

            updated_task = await task_service.get_task(session, task_id)
            await session.refresh(updated_task)
            assert updated_task.is_running is True

            child_gate.set()
            await child_finished.wait()

    async def test_cancel_session_cascades_to_nested_subagent_sessions_without_deactivating_them(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        parent_session_id = payload["session_id"]
        task_id = payload["task_id"]

        child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:parent",
            agent_key="writer",
            dispatch_id="dispatch-parent",
            tool_call_id="tool-call-parent",
            request={"task": "write", "input": {}, "metadata": {}},
            status="running",
        )
        nested_child = await create_child_run(
            session,
            parent_session_id=child.child_thread_id,
            parent_task_id=task_id,
            parent_thread_id=child.child_thread_id,
            child_thread_id=f"{child.child_thread_id}:child:nested",
            agent_key="reviewer",
            dispatch_id="dispatch-nested",
            tool_call_id="tool-call-nested",
            request={"task": "review", "input": {}, "metadata": {}},
            status="running",
        )

        fake_registry = SimpleNamespace(
            cancel=AsyncMock(return_value=True),
        mark_cancelled=AsyncMock(return_value=None),
        cancel_task=AsyncMock(return_value=False),
            clear_cancelled=AsyncMock(),
            register=AsyncMock(),
            unregister=AsyncMock(return_value=True),
            is_running=AsyncMock(return_value=False),
            is_parent_running=AsyncMock(return_value=False),
        )

        with patch.object(_SESSION_RUNNERS[parent_session_id], "cancel") as runner_cancel, patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ):
            response = await client.post(
                f"/api/v1/agent/sessions/{parent_session_id}/cancel"
            )

        assert response.status_code == status.HTTP_200_OK
        runner_cancel.assert_called_once_with()
        cancelled_session_ids = [item.args[0] for item in fake_registry.cancel.await_args_list]
        assert {
            parent_session_id,
            child.child_thread_id,
        }.issubset(set(cancelled_session_ids))

        parent_children = await client.get(
            f"/api/v1/agent/sessions/{parent_session_id}/subagents"
        )
        nested_children = await client.get(
            f"/api/v1/agent/sessions/{child.child_thread_id}/subagents"
        )
        assert parent_children.status_code == status.HTTP_200_OK
        assert nested_children.status_code == status.HTTP_200_OK
        assert parent_children.json() == [
            {
                "child_run_id": child.id,
                "child_thread_id": child.child_thread_id,
                "agent_key": "writer",
                "agent_number": child.metadata_json["agent_number"],
                "status": "cancelled",
                "queued_messages": 0,
                "is_active": True,
                "pending_approval": None,
            },
        ]
        assert nested_children.json() == [
            {
                "child_run_id": nested_child.id,
                "child_thread_id": nested_child.child_thread_id,
                "agent_key": "reviewer",
                "agent_number": nested_child.metadata_json["agent_number"],
                "status": "cancelled",
                "queued_messages": 0,
                "is_active": True,
                "pending_approval": None,
            },
        ]

    async def test_cancel_session_keeps_completed_subagent_status_unchanged(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        parent_session_id = payload["session_id"]
        task_id = payload["task_id"]

        completed_child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:completed",
            agent_key="writer",
            dispatch_id="dispatch-completed",
            tool_call_id="tool-call-completed",
            request={"task": "write", "input": {}, "metadata": {}},
            status="completed",
        )
        running_child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:running",
            agent_key="reviewer",
            dispatch_id="dispatch-running",
            tool_call_id="tool-call-running",
            request={"task": "review", "input": {}, "metadata": {}},
            status="running",
        )

        fake_registry = SimpleNamespace(
            cancel=AsyncMock(return_value=True),
        mark_cancelled=AsyncMock(return_value=None),
        cancel_task=AsyncMock(return_value=False),
            clear_cancelled=AsyncMock(),
            register=AsyncMock(),
            unregister=AsyncMock(return_value=True),
            is_running=AsyncMock(return_value=False),
            is_parent_running=AsyncMock(return_value=False),
        )

        with patch.object(_SESSION_RUNNERS[parent_session_id], "cancel") as runner_cancel, patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ):
            response = await client.post(
                f"/api/v1/agent/sessions/{parent_session_id}/cancel"
            )

        assert response.status_code == status.HTTP_200_OK
        runner_cancel.assert_called_once_with()

        await session.refresh(completed_child)
        await session.refresh(running_child)
        assert completed_child.status == "completed"
        assert running_child.status == "cancelled"

        children_response = await client.get(
            f"/api/v1/agent/sessions/{parent_session_id}/subagents"
        )
        assert children_response.status_code == status.HTTP_200_OK
        assert children_response.json() == [
            {
                "child_run_id": completed_child.id,
                "child_thread_id": completed_child.child_thread_id,
                "agent_key": "writer",
                "agent_number": completed_child.metadata_json["agent_number"],
                "status": "completed",
                "queued_messages": 0,
                "is_active": True,
                "pending_approval": None,
            },
            {
                "child_run_id": running_child.id,
                "child_thread_id": running_child.child_thread_id,
                "agent_key": "reviewer",
                "agent_number": running_child.metadata_json["agent_number"],
                "status": "cancelled",
                "queued_messages": 0,
                "is_active": True,
                "pending_approval": None,
            },
        ]

    async def test_cancel_session_publishes_cancelled_subagent_status_to_parent_stream(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        buffer = get_agent_event_replay_buffer()
        buffer.clear_all()
        try:
            target = await _seed_agent_target(client)
            session_response = await client.post(
                "/api/v1/agent/sessions",
                json={
                    "project_id": target["project_id"],
    
                    "model_id": target["model_id"],
                    "max_iterations": 5,
                },
            )
            payload = session_response.json()
            parent_session_id = payload["session_id"]
            task_id = payload["task_id"]

            child = await create_child_run(
                session,
                parent_session_id=parent_session_id,
                parent_task_id=task_id,
                parent_thread_id=parent_session_id,
                child_thread_id=f"{parent_session_id}:child:parent",
                agent_key="writer",
                dispatch_id="dispatch-parent",
                tool_call_id="tool-call-parent",
                request={"task": "write", "input": {}, "metadata": {}},
                status="running",
            )

            fake_registry = SimpleNamespace(
                cancel=AsyncMock(return_value=True),
        mark_cancelled=AsyncMock(return_value=None),
        cancel_task=AsyncMock(return_value=False),
                clear_cancelled=AsyncMock(),
                register=AsyncMock(),
                unregister=AsyncMock(return_value=True),
                is_running=AsyncMock(return_value=False),
                is_parent_running=AsyncMock(return_value=False),
            )
            emit_mock = AsyncMock()

            with patch.object(
                _SESSION_RUNNERS[parent_session_id],
                "cancel",
            ) as runner_cancel, patch(
                "app.api.routers.agent_runtime.get_agent_run_registry",
                return_value=fake_registry,
            ), patch(
                "app.api.routers.agent_runtime.emit",
                new=emit_mock,
            ), patch(
                "app.agent_runtime.runner.subagent_runner.emit",
                new=emit_mock,
            ):
                response = await client.post(
                    f"/api/v1/agent/sessions/{parent_session_id}/cancel"
                )

            assert response.status_code == status.HTTP_200_OK
            runner_cancel.assert_called_once_with()

            replayed = buffer.replay_events_unlocked(parent_session_id)
            cancelled_statuses = [
                event.data
                for event in replayed
                if event.name == "agent:subagent_status"
                and event.data.get("child_run_id") == child.id
            ]
            assert cancelled_statuses == [
                {
                    "parent_session_id": parent_session_id,
                    "child_run_id": child.id,
                    "child_thread_id": child.child_thread_id,
                    "agent_key": "writer",
                    "agent_number": child.metadata_json["agent_number"],
                    "status": "cancelled",
                    "queued_messages": 0,
                    "is_active": True,
                    "pending_approval": None,
                }
            ]
            emit_mock.assert_any_await(
                "agent:subagent_status",
                cancelled_statuses[0],
                room=agent_subagents_room(parent_session_id),
            )
        finally:
            buffer.clear_all()

    async def test_cancel_subagent_session_cancels_child_task_and_marks_cancelled(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        parent_session_id = payload["session_id"]
        task_id = payload["task_id"]

        child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:cancel",
            agent_key="writer",
            dispatch_id="dispatch-cancel",
            tool_call_id="tool-call-cancel",
            request={"task": "write", "input": {}, "metadata": {}},
            status="running",
        )

        task_started = asyncio.Event()
        task_finished = asyncio.Event()

        async def fake_child() -> None:
            task_started.set()
            try:
                await asyncio.sleep(60)
            finally:
                task_finished.set()

        child_task = asyncio.create_task(fake_child())
        await get_agent_run_registry().register_child(
            parent_session_id, child.id, child_task
        )
        try:
            await task_started.wait()

            emit_mock = AsyncMock()
            with patch(
                "app.api.routers.agent_runtime.emit",
                new=emit_mock,
            ), patch(
                "app.agent_runtime.runner.subagent_runner.emit",
                new=emit_mock,
            ):
                response = await client.post(
                    f"/api/v1/agent/sessions/{parent_session_id}/subagents/{child.id}/cancel"
                )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True

            await asyncio.wait_for(task_finished.wait(), timeout=2)
            assert child_task.cancelled() is True

            await session.refresh(child)
            assert child.status == "cancelled"
            assert child.is_active is True
            assert child.error == "user cancelled subagent"

            request_row = (
                await session.execute(
                    select(AgentChildRunRequest).where(
                        AgentChildRunRequest.child_run_id == child.id
                    )
                )
            ).scalar_one()
            assert request_row.status == "cancelled"
            assert request_row.error == "user cancelled subagent"
        finally:
            await get_agent_run_registry().unregister_child(parent_session_id, child.id)

    async def test_cancel_subagent_session_returns_404_for_unknown_child(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        response = await client.post(
            "/api/v1/agent/sessions/unknown-parent/subagents/unknown-child/cancel"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_cancel_subagent_session_is_noop_for_terminal_child(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        parent_session_id = payload["session_id"]
        task_id = payload["task_id"]

        child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:terminal",
            agent_key="writer",
            dispatch_id="dispatch-terminal",
            tool_call_id="tool-call-terminal",
            request={"task": "write", "input": {}, "metadata": {}},
            status="completed",
        )

        response = await client.post(
            f"/api/v1/agent/sessions/{parent_session_id}/subagents/{child.id}/cancel"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

        await session.refresh(child)
        assert child.status == "completed"
        assert child.error is None

    async def test_cancel_session_starts_new_run_after_cancelled_revision(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task_id = payload["task_id"]

        user_message = await message_repo.insert_message(
            session,
            session_id=session_id,
            task_id=task_id,
            project_id=target["project_id"],
            role="user",
            status="sent",
            content="继续处理当前问题",
        )
        revision = await begin_user_revision(
            session,
            project_id=target["project_id"],
            task_id=task_id,
            agent_session_id=session_id,
            user_message_id=user_message.id,
            user_message_seq=user_message.seq,
            message="用户消息: 继续处理当前问题",
            pre_run_checkpoint_id="cp-before-cancelled-run",
            graph_thread_id=session_id,
        )
        revision.status = "cancelled"
        session.add(revision)
        await session.commit()

        fake_registry = SimpleNamespace(
            cancel=AsyncMock(return_value=True),
        mark_cancelled=AsyncMock(return_value=None),
        cancel_task=AsyncMock(return_value=False),
            clear_cancelled=AsyncMock(),
            register=AsyncMock(),
            unregister=AsyncMock(return_value=True),
            is_running=AsyncMock(return_value=False),
            is_parent_running=AsyncMock(return_value=False),
        )
        with patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(return_value=None),
        ) as mock_run:
            cancel_response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/cancel"
            )
            assert cancel_response.status_code == status.HTTP_200_OK

            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "取消上一轮后重新开始"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        await asyncio.sleep(0.05)
        mock_run.assert_awaited_once_with(user_request="取消上一轮后重新开始")

    async def test_cancel_does_not_cancel_run_waiting_to_start(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="active revision",
            agent_session_id=session_id,
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Active revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        finalize_entered = asyncio.Event()
        release_finalize = asyncio.Event()
        emit_entered = asyncio.Event()
        release_emit = asyncio.Event()
        run_started = asyncio.Event()
        release_run = asyncio.Event()
        run_saw_cancel = False
        runner = _SESSION_RUNNERS[session_id]

        async def block_finalize(*args: Any, **kwargs: Any) -> None:
            finalize_entered.set()
            await release_finalize.wait()

        async def fake_run(self: SessionRunner, *, user_request: str, **kwargs: Any) -> None:
            nonlocal run_saw_cancel
            self._cancel_event.clear()
            run_started.set()
            await release_run.wait()
            run_saw_cancel = self._cancel_event.is_set()

        async def block_cancel_notification(
            event_name: str, payload: dict[str, Any], **kwargs: Any
        ) -> None:
            if payload.get("is_running") is False:
                emit_entered.set()
                await release_emit.wait()

        with patch(
            "app.api.routers.agent_runtime.finalize_revision_status",
            new=block_finalize,
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=fake_run,
        ), patch(
            "app.api.routers.agent_runtime.emit",
            new=block_cancel_notification,
        ):
            cancel_task = asyncio.create_task(
                client.post(f"/api/v1/agent/sessions/{session_id}/cancel")
            )
            await finalize_entered.wait()
            send_task = asyncio.create_task(
                client.post(
                    f"/api/v1/agent/sessions/{session_id}/message",
                    json={"message": "start after cancel"},
                )
            )
            await asyncio.sleep(0.05)
            assert not run_started.is_set()
            assert not send_task.done()

            release_finalize.set()
            await emit_entered.wait()
            await asyncio.sleep(0.05)
            assert not run_started.is_set()

            release_emit.set()
            cancel_response = await cancel_task
            send_response = await send_task
            assert cancel_response.status_code == status.HTTP_200_OK
            assert send_response.status_code == status.HTTP_200_OK
            await run_started.wait()
            release_run.set()
            await asyncio.sleep(0.05)

        assert run_saw_cancel is False
        assert runner._cancel_event.is_set() is False

    async def test_launch_task_returns_when_cancelled_before_start(self) -> None:
        registry = get_agent_run_registry()
        state_update_entered = asyncio.Event()
        release_state_update = asyncio.Event()

        async def block_state_update(**kwargs: Any) -> None:
            state_update_entered.set()
            await release_state_update.wait()

        async def should_not_run() -> None:
            raise AssertionError("cancelled task must not enter its coroutine")

        launch_task = asyncio.create_task(
            _launch_task(
                db_session_factory=lambda: None,
                session_id="launch-race",
                task_id="task-id",
                project_id="project-id",
                coro=should_not_run(),
            )
        )
        try:
            with patch(
                "app.api.routers.agent_runtime._set_task_running_state",
                new=block_state_update,
            ):
                await asyncio.wait_for(state_update_entered.wait(), timeout=1)
                assert await registry.cancel("launch-race") is True
                release_state_update.set()
                await asyncio.wait_for(launch_task, timeout=1)
        finally:
            release_state_update.set()
            if not launch_task.done():
                launch_task.cancel()
            await asyncio.gather(launch_task, return_exceptions=True)

        assert await registry.is_running("launch-race") is False

    async def test_cancel_succeeds_when_post_commit_cleanup_fails(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="active revision",
            agent_session_id=session_id,
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Active revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        registry = get_agent_run_registry()
        parent_task = asyncio.create_task(asyncio.Event().wait())
        await registry.register(session_id, parent_task)

        with patch(
            "app.api.routers.agent_runtime._cancel_subagent_session_tree",
            new=AsyncMock(side_effect=RuntimeError("cleanup failed")),
        ), patch(
            "app.api.routers.agent_runtime.emit",
            new=AsyncMock(side_effect=RuntimeError("notification failed")),
        ):
            response = await client.post(f"/api/v1/agent/sessions/{session_id}/cancel")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        await session.refresh(task)
        await session.refresh(revision)
        assert task.is_running is False
        assert revision.status == "cancelled"
        await asyncio.gather(parent_task, return_exceptions=True)
        assert parent_task.cancelled()

    async def test_send_does_not_queue_after_concurrent_cancellation(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task = await task_service.get_task(session, payload["task_id"])
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="active revision",
            agent_session_id=session_id,
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Active revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        registry = get_agent_run_registry()
        parent_task = asyncio.create_task(asyncio.Event().wait())
        await registry.register(session_id, parent_task)
        runner = _SESSION_RUNNERS[session_id]
        finalize_entered = asyncio.Event()
        release_finalize = asyncio.Event()

        async def block_finalize(*args: Any, **kwargs: Any) -> None:
            finalize_entered.set()
            await release_finalize.wait()

        queue_message = AsyncMock(
            return_value={
                "message_id": "should-not-queue",
                "content": "消息",
                "created_at": "2026-06-12T00:00:00+00:00",
            }
        )
        launch_task = AsyncMock(side_effect=lambda **kwargs: kwargs["coro"].close())
        cancel_request = None
        send_request = None
        try:
            with (
                patch(
                    "app.api.routers.agent_runtime.finalize_revision_status",
                    new=block_finalize,
                ),
                patch.object(runner, "queue_pending_user_message", new=queue_message),
                patch(
                    "app.api.routers.agent_runtime.SessionRunner.run",
                    new=AsyncMock(return_value=None),
                ),
                patch("app.api.routers.agent_runtime._launch_task", new=launch_task),
                patch(
                    "app.api.routers.agent_runtime._cancel_subagent_session_tree",
                    new=AsyncMock(),
                ),
                patch("app.api.routers.agent_runtime.emit", new=AsyncMock()),
            ):
                cancel_request = asyncio.create_task(
                    client.post(f"/api/v1/agent/sessions/{session_id}/cancel")
                )
                await asyncio.wait_for(finalize_entered.wait(), timeout=1)

                send_request = asyncio.create_task(
                    client.post(
                        f"/api/v1/agent/sessions/{session_id}/message",
                        json={"message": "并发消息"},
                    )
                )
                await asyncio.sleep(0.05)
                assert not send_request.done()
                queue_message.assert_not_awaited()

                release_finalize.set()
                cancel_response = await cancel_request
                send_response = await send_request

            assert cancel_response.status_code == status.HTTP_200_OK
            assert send_response.status_code == status.HTTP_200_OK
            queue_message.assert_not_awaited()
            launch_task.assert_awaited_once()
        finally:
            release_finalize.set()
            pending_requests = [request for request in (cancel_request, send_request) if request]
            for request in pending_requests:
                if not request.done():
                    request.cancel()
            await asyncio.gather(*pending_requests, return_exceptions=True)
            if not parent_task.done():
                parent_task.cancel()
            await asyncio.gather(parent_task, return_exceptions=True)

    async def test_get_session_state_reads_persisted_session_without_runner(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        _SESSION_RUNNERS.clear()

        response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == session_id
        assert data["is_running"] is False
        assert data["state"]["model_config"]["model_id"] == "gpt-3.5-turbo"
        assert session_id not in _SESSION_RUNNERS

    async def test_get_session_state_allows_deleted_model_without_runner(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        delete_response = await client.delete(f"/api/v1/models/{target['model_id']}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        _SESSION_RUNNERS.clear()

        response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["state"]["model_config"]["model_record_id"] == target["model_id"]
        assert session_id not in _SESSION_RUNNERS

    async def test_get_session_state_reads_legacy_model_config_without_record_id(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        runner = _SESSION_RUNNERS[session_id]
        graph = await runner._get_graph()
        state = await graph.aget_state({"configurable": {"thread_id": session_id}})
        legacy_model_config = dict(state.values["model_config"])
        legacy_model_config.pop("model_record_id")
        await graph.aupdate_state(
            {"configurable": {"thread_id": session_id}},
            {"model_config": legacy_model_config},
            as_node="primary",
        )
        _SESSION_RUNNERS.clear()

        response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        assert "model_record_id" not in response.json()["state"]["model_config"]
        assert session_id not in _SESSION_RUNNERS

    async def test_agent_checkpoint_and_session_state_do_not_contain_api_key(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        checkpointer = await get_checkpointer()
        checkpoint = await checkpointer.aget_tuple(
            {"configurable": {"thread_id": session_id}}
        )

        assert checkpoint is not None
        persisted_model_config = checkpoint.checkpoint["channel_values"]["model_config"]
        assert "api_key" not in persisted_model_config

        _SESSION_RUNNERS.clear()
        response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        assert "api_key" not in response.json()["state"]["model_config"]

    async def test_list_subagent_sessions_returns_only_active_state_rows(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        parent_session_id = payload["session_id"]
        task_id = payload["task_id"]

        queued_child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:queued",
            agent_key="writer",
            dispatch_id="dispatch-queued",
            tool_call_id="tool-call-queued",
            request={"task": "write", "input": {}, "metadata": {}},
            status="queued",
        )
        waiting_child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:waiting",
            agent_key="reviewer",
            dispatch_id="dispatch-waiting",
            tool_call_id="tool-call-waiting",
            request={"task": "review", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            waiting_child.id,
            approval_id="approval-waiting",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-waiting",
                "tool_name": "review_chapter",
                "tool_args": {"chapter_id": "chapter-1"},
                "child_run_id": waiting_child.id,
            },
        )
        inactive_child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:inactive",
            agent_key="composer",
            dispatch_id="dispatch-inactive",
            tool_call_id="tool-call-inactive",
            request={"task": "compose", "input": {}, "metadata": {}},
            status="completed",
        )
        inactive_child.is_active = False
        inactive_child.last_assistant_content = "should-not-leak"
        session.add(inactive_child)
        await session.commit()
        await session.refresh(inactive_child)

        response = await client.get(
            f"/api/v1/agent/sessions/{parent_session_id}/subagents"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == [
            {
                "child_run_id": queued_child.id,
                "child_thread_id": queued_child.child_thread_id,
                "agent_key": "writer",
                "agent_number": queued_child.metadata_json["agent_number"],
                "status": "queued",
                "queued_messages": await count_pending_child_run_requests(
                    session, queued_child.id
                ),
                "is_active": True,
                "pending_approval": None,
            },
            {
                "child_run_id": waiting_child.id,
                "child_thread_id": waiting_child.child_thread_id,
                "agent_key": "reviewer",
                "agent_number": waiting_child.metadata_json["agent_number"],
                "status": "waiting_user",
                "queued_messages": await count_pending_child_run_requests(
                    session, waiting_child.id
                ),
                "is_active": True,
                "pending_approval": {
                    "type": "tool_approval",
                    "approval_id": "approval-waiting",
                    "tool_name": "review_chapter",
                    "tool_args": {"chapter_id": "chapter-1"},
                    "child_run_id": waiting_child.id,
                },
            },
        ]
        for item in data:
            assert set(item.keys()) == {
                "child_run_id",
                "child_thread_id",
                "agent_key",
                "agent_number",
                "status",
                "queued_messages",
                "is_active",
                "pending_approval",
            }
            assert "last_assistant_content" not in item
            assert "assistant_summary" not in item
            assert "messages" not in item

    async def test_get_subagent_session_returns_metadata_messages_and_running_state(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        from app.agent_runtime.runner.run_registry import get_agent_run_registry

        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        parent_session_id = payload["session_id"]
        task_id = payload["task_id"]

        child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task_id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:detail",
            agent_key="writer",
            dispatch_id="dispatch-detail",
            tool_call_id="tool-call-detail",
            request={"task": "write", "input": {"chapter": 1}, "metadata": {}},
            status="running",
            metadata={
                "priority": "high",
                "token_usage": {
                    "token_input": 120,
                    "token_output": 48,
                    "token_cache": 16,
                    "context_input_tokens": 72,
                    "context_length": 8000,
                },
            },
        )
        await message_repo.insert_message(
            session,
            session_id=child.child_thread_id,
            task_id=task_id,
            project_id=target["project_id"],
            role="user",
            status="sent",
            content="请起草这一章",
            agent_id="primary",
        )
        assistant_message = await message_repo.insert_message(
            session,
            session_id=child.child_thread_id,
            task_id=task_id,
            project_id=target["project_id"],
            role="assistant",
            status="complete",
            content="这是子 agent 的回复",
            agent_id="writer",
        )

        gate = asyncio.Event()

        async def _wait_for_gate() -> None:
            await gate.wait()

        child_task = asyncio.create_task(_wait_for_gate())
        await get_agent_run_registry().register_child(
            parent_session_id,
            child.id,
            child_task,
        )
        try:
            response = await client.get(f"/api/v1/agent/subagents/{child.id}")
        finally:
            gate.set()
            await asyncio.gather(child_task, return_exceptions=True)
            await get_agent_run_registry().unregister_child(parent_session_id, child.id)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["child_run_id"] == child.id
        assert data["parent_session_id"] == parent_session_id
        assert data["parent_task_id"] == task_id
        assert data["parent_thread_id"] == parent_session_id
        assert data["child_thread_id"] == child.child_thread_id
        assert data["agent_key"] == "writer"
        assert data["agent_number"] == child.metadata_json["agent_number"]
        assert "dispatch_mode" not in data
        assert data["status"] == "running"
        assert data["queued_messages"] == 0
        assert data["is_active"] is True
        assert data["is_running"] is True
        assert data["metadata"] == {
            "priority": "high",
            "agent_number": child.metadata_json["agent_number"],
        }
        assert data["token_input"] == 120
        assert data["token_output"] == 48
        assert data["token_cache"] == 16
        assert data["context_input_tokens"] == 72
        assert data["context_length"] == 8000
        assert data["request"] == {
            "task": "write",
            "input": {"chapter": 1},
            "metadata": {},
        }
        assert data["messages"] == [
            {
                "id": data["messages"][0]["id"],
                "task_id": task_id,
                "role": "user",
                "agent_id": "primary",
                "content": "请起草这一章",
                "tool_calls": [],
                "tool_call_id": None,
                "metadata": {},
                "message_type": "user_request",
                "message_status": "completed",
                "display_channel": "list",
                "payload": {"kind": "user_request"},
                "correlation_id": data["messages"][0]["correlation_id"],
                "created_at": data["messages"][0]["created_at"],
                "updated_at": data["messages"][0]["updated_at"],
            },
            {
                "id": f"{assistant_message.id}:text",
                "task_id": task_id,
                "role": "assistant",
                "agent_id": "writer",
                "content": "这是子 agent 的回复",
                "tool_calls": [],
                "tool_call_id": None,
                "metadata": {},
                "message_type": "text",
                "message_status": "completed",
                "display_channel": "list",
                "payload": {"kind": "assistant_output"},
                "correlation_id": assistant_message.id,
                "created_at": data["messages"][1]["created_at"],
                "updated_at": data["messages"][1]["updated_at"],
            },
        ]

    async def test_send_message_rehydrates_persisted_session_without_runner(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        _SESSION_RUNNERS.clear()

        with patch("app.api.routers.agent_runtime.SessionRunner.run", new=AsyncMock(return_value=None)) as mock_run:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "帮我继续这一轮"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        await asyncio.sleep(0.05)
        mock_run.assert_awaited_once_with(user_request="帮我继续这一轮")
        assert session_id in _SESSION_RUNNERS

    async def test_send_message_starts_new_run_for_paused_graph(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        with patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(return_value=None),
        ) as mock_run:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "根据当前审核继续处理"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        await asyncio.sleep(0.05)
        mock_run.assert_awaited_once_with(user_request="根据当前审核继续处理")

    async def test_send_message_queues_follow_up_while_parent_run_is_active(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        runner = _SESSION_RUNNERS[session_id]
        fake_registry = SimpleNamespace(
            is_running=AsyncMock(return_value=True),
            is_cancelled=AsyncMock(return_value=False),
        )

        with patch.object(
            runner,
            "queue_pending_user_message",
            new=AsyncMock(return_value={
                "message_id": "msg_pending_1",
                "content": "补充要求：保留上一段语气",
                "created_at": "2026-06-12T00:00:00+00:00",
            }),
            create=True,
        ) as mock_queue, patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.run",
            new=AsyncMock(return_value=None),
        ) as mock_run:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/message",
                json={"message": "补充要求：保留上一段语气"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        assert response.json()["queued"] is True
        assert response.json()["pending_message"] == {
            "message_id": "msg_pending_1",
            "content": "补充要求：保留上一段语气",
            "created_at": "2026-06-12T00:00:00+00:00",
        }
        await asyncio.sleep(0.05)
        mock_queue.assert_awaited_once_with("补充要求：保留上一段语气")
        mock_run.assert_not_awaited()

    async def test_cancel_pending_message_restores_message_content(
        self,
        client: AsyncClient,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        runner = _SESSION_RUNNERS[session_id]

        with patch.object(
            runner,
            "cancel_pending_user_message",
            AsyncMock(return_value={
                "message_id": "msg_pending_1",
                "content": "补充要求：保留上一段语气",
                "created_at": "2026-06-12T00:00:00+00:00",
            }),
            create=True,
        ) as mock_cancel:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/pending-message/cancel",
                json={"message_id": "msg_pending_1"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "success": True,
            "session_id": session_id,
            "message_id": "msg_pending_1",
            "restored_message_content": "补充要求：保留上一段语气",
        }
        mock_cancel.assert_awaited_once_with("msg_pending_1")

    async def test_submit_tool_approval_launches_resume(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        with patch("app.api.routers.agent_runtime.SessionRunner.resume", new=AsyncMock(return_value=None)) as mock_resume:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/tool-approval",
                json={"approval_id": "approval-1", "approved": True},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True
            await asyncio.sleep(0.05)
            mock_resume.assert_awaited_once_with({
                "action_type": "tool_approval",
                "approval_id": "approval-1",
                "approved": True,
            })

    async def test_submit_tool_approval_routes_idle_child_approval_to_subagent_resume(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task_id = payload["task_id"]
        row = await create_child_run(
            session,
            parent_session_id=session_id,
            parent_task_id=task_id,
            parent_thread_id=session_id,
            child_thread_id=f"{session_id}:child:approval",
            agent_key="writer",
            dispatch_id="dispatch-child",
            tool_call_id="tool-call-child",
            request={"task": "write", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-child-api",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-child-api",
                "child_run_id": row.id,
            },
        )
        task = await task_service.get_task(session, task_id)
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="active parent revision",
            agent_session_id=session_id,
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Active parent revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        with patch(
            "app.api.routers.agent_runtime.SessionRunner.resume",
            new=AsyncMock(return_value=None),
        ) as mock_parent_resume, patch(
            "app.api.routers.agent_runtime._launch_task",
            new=AsyncMock(side_effect=AssertionError("child approvals must not launch a parent task")),
        ) as mock_launch_task, patch(
            "app.api.routers.agent_runtime.ensure_child_processing",
            new=AsyncMock(return_value=True),
        ) as mock_ensure_child_processing:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/tool-approval",
                json={"approval_id": "approval-child-api", "approved": True},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        mock_ensure_child_processing.assert_awaited_once()
        assert mock_ensure_child_processing.await_args is not None
        ensure_kwargs = mock_ensure_child_processing.await_args.kwargs
        assert ensure_kwargs["parent_session_id"] == session_id
        assert ensure_kwargs["child_run_id"] == row.id
        assert ensure_kwargs["resume_payload"] == {
            "action_type": "tool_approval",
            "approval_id": "approval-child-api",
            "approved": True,
        }
        assert type(ensure_kwargs["runner"]).__name__ == "SubagentRunner"
        mock_launch_task.assert_not_awaited()
        mock_parent_resume.assert_not_awaited()

    async def test_submit_tool_approval_routes_sync_child_approval_to_subagent_processing(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task_id = payload["task_id"]
        row = await create_child_run(
            session,
            parent_session_id=session_id,
            parent_task_id=task_id,
            parent_thread_id=session_id,
            child_thread_id=f"{session_id}:child:sync-approval",
            agent_key="composer",
            dispatch_id="dispatch-child-sync",
            tool_call_id="tool-call-child-sync",
            request={"task": "make a plan", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-child-sync-api",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-child-sync-api",
                "child_run_id": row.id,
            },
        )

        with patch(
            "app.api.routers.agent_runtime._launch_task",
            new=AsyncMock(side_effect=AssertionError("sync child approvals must not launch a parent task")),
        ) as mock_launch_task, patch(
            "app.api.routers.agent_runtime.SessionRunner.resume",
            new=AsyncMock(return_value=None),
        ) as mock_parent_resume, patch(
            "app.api.routers.agent_runtime.ensure_child_processing",
            new=AsyncMock(return_value=True),
        ) as mock_ensure_child_processing:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/tool-approval",
                json={"approval_id": "approval-child-sync-api", "approved": True},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        mock_ensure_child_processing.assert_awaited_once()
        assert mock_ensure_child_processing.await_args is not None
        ensure_kwargs = mock_ensure_child_processing.await_args.kwargs
        assert ensure_kwargs["parent_session_id"] == session_id
        assert ensure_kwargs["child_run_id"] == row.id
        assert ensure_kwargs["resume_payload"] == {
            "action_type": "tool_approval",
            "approval_id": "approval-child-sync-api",
            "approved": True,
        }
        assert type(ensure_kwargs["runner"]).__name__ == "SubagentRunner"
        mock_launch_task.assert_not_awaited()
        mock_parent_resume.assert_not_awaited()

    async def test_submit_tool_approval_keeps_active_parent_revision_on_child_launch_failure(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task_id = payload["task_id"]
        row = await create_child_run(
            session,
            parent_session_id=session_id,
            parent_task_id=task_id,
            parent_thread_id=session_id,
            child_thread_id=f"{session_id}:child:launch-failure",
            agent_key="writer",
            dispatch_id="dispatch-child-launch-failure",
            tool_call_id="tool-call-child-launch-failure",
            request={"task": "write", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-child-launch-failure",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-child-launch-failure",
                "child_run_id": row.id,
            },
        )
        task = await task_service.get_task(session, task_id)
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="active parent revision",
            agent_session_id=session_id,
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Active parent revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        async def fail_child_processing(**kwargs: Any) -> bool:
            raise RuntimeError("child launch failed")

        with patch(
            "app.api.routers.agent_runtime.ensure_child_processing",
            new=fail_child_processing,
        ):
            with pytest.raises(RuntimeError, match="child launch failed"):
                await client.post(
                    f"/api/v1/agent/sessions/{session_id}/tool-approval",
                    json={"approval_id": "approval-child-launch-failure", "approved": True},
                )

        await session.refresh(revision)
        assert revision.status == "active"
        await session.refresh(task)
        assert task.is_running is False

    async def test_cancel_blocks_child_approval_before_it_marks_task_running(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={"project_id": target["project_id"], "model_id": target["model_id"]},
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task_id = payload["task_id"]
        row = await create_child_run(
            session,
            parent_session_id=session_id,
            parent_task_id=task_id,
            parent_thread_id=session_id,
            child_thread_id=f"{session_id}:child:cancel-race",
            agent_key="writer",
            dispatch_id="dispatch-child-cancel-race",
            tool_call_id="tool-call-child-cancel-race",
            request={"task": "write", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-child-cancel-race",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-child-cancel-race",
                "child_run_id": row.id,
            },
        )
        task = await task_service.get_task(session, task_id)
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="active parent revision",
            agent_session_id=session_id,
            revision_type="agent",
            status="active",
            is_checkpoint=True,
            project_snapshot_title="Active parent revision",
            project_snapshot_word_count=0,
            project_snapshot_chapter_count=0,
        )
        session.add(revision)
        await session.flush()
        task.current_revision_id = revision.id
        session.add(task)
        await session.commit()

        finalize_entered = asyncio.Event()
        release_finalize = asyncio.Event()

        async def block_finalize(
            finalize_session,
            revision_id: str,
            revision_status: str,
        ) -> None:
            assert revision_id == revision.id
            assert revision_status == "cancelled"
            finalize_entered.set()
            await release_finalize.wait()
            revision.status = revision_status
            finalize_session.add(revision)

        with patch(
            "app.api.routers.agent_runtime.finalize_revision_status",
            new=block_finalize,
        ), patch(
            "app.api.routers.agent_runtime.ensure_child_processing",
            new=AsyncMock(return_value=True),
        ) as mock_ensure_child_processing, patch(
            "app.api.routers.agent_runtime.emit",
            new=AsyncMock(),
        ):
            cancel_task = asyncio.create_task(
                client.post(f"/api/v1/agent/sessions/{session_id}/cancel")
            )
            await finalize_entered.wait()
            approval_task = asyncio.create_task(
                client.post(
                    f"/api/v1/agent/sessions/{session_id}/tool-approval",
                    json={"approval_id": "approval-child-cancel-race", "approved": True},
                )
            )
            await asyncio.sleep(0.05)
            assert not approval_task.done()
            mock_ensure_child_processing.assert_not_awaited()

            release_finalize.set()
            cancel_response = await cancel_task
            approval_response = await approval_task

        assert cancel_response.status_code == status.HTTP_200_OK
        assert approval_response.status_code == status.HTTP_409_CONFLICT
        assert approval_response.json()["detail"]["code"] == "session_cancelled"
        mock_ensure_child_processing.assert_not_awaited()
        await session.refresh(task)
        await session.refresh(revision)
        assert task.is_running is False
        assert revision.status == "cancelled"

    async def test_submit_tool_approval_for_sync_child_does_not_cancel_parent_wait_task(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        from app.agent_runtime.runner.run_registry import get_agent_run_registry

        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        payload = session_response.json()
        session_id = payload["session_id"]
        task_id = payload["task_id"]
        row = await create_child_run(
            session,
            parent_session_id=session_id,
            parent_task_id=task_id,
            parent_thread_id=session_id,
            child_thread_id=f"{session_id}:child:sync-approval-parent-wait",
            agent_key="composer",
            dispatch_id="dispatch-child-sync-parent-wait",
            tool_call_id="tool-call-child-sync-parent-wait",
            request={"task": "make a plan", "input": {}, "metadata": {}},
            status="waiting_user",
        )
        await record_child_run_pending_approval(
            session,
            row.id,
            approval_id="approval-child-sync-parent-wait",
            approval_request={
                "type": "tool_approval",
                "approval_id": "approval-child-sync-parent-wait",
                "child_run_id": row.id,
            },
        )

        registry = get_agent_run_registry()
        gate = asyncio.Event()

        async def _wait_for_parent_gate() -> None:
            await gate.wait()

        parent_wait_task = asyncio.create_task(_wait_for_parent_gate())
        await registry.register(session_id, parent_wait_task)
        try:
            with patch(
                "app.api.routers.agent_runtime.ensure_child_processing",
                new=AsyncMock(return_value=True),
            ):
                response = await client.post(
                    f"/api/v1/agent/sessions/{session_id}/tool-approval",
                    json={
                        "approval_id": "approval-child-sync-parent-wait",
                        "approved": True,
                    },
                )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True
            await asyncio.sleep(0.05)
            assert not parent_wait_task.cancelled()
            assert await registry.is_parent_running(session_id) is True
        finally:
            gate.set()
            await asyncio.gather(parent_wait_task, return_exceptions=True)
            await registry.unregister(session_id, parent_wait_task)

    async def test_submit_question_answer_launches_resume(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],

                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]

        with patch("app.api.routers.agent_runtime.SessionRunner.resume", new=AsyncMock(return_value=None)) as mock_resume:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/question-answer",
                json={
                    "action_id": "question-1",
                    "answer": [{"question": "风格选择", "answer": "正式"}],
                },
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True
            await asyncio.sleep(0.05)
            mock_resume.assert_awaited_once_with({
                "action_type": "clarification",
                "action_id": "question-1",
                "answer": [{"question": "风格选择", "answer": "正式"}],
            })

    async def test_submit_interrupt_batch_launches_single_resume(self, client: AsyncClient) -> None:
        target = await _seed_agent_target(client)
        session_response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
            },
        )
        session_id = session_response.json()["session_id"]
        responses = [
            {
                "interrupt_id": "approval-1",
                "action_type": "tool_approval",
                "approval_id": "approval-1",
                "approved": True,
            },
            {
                "interrupt_id": "question-1",
                "action_type": "clarification",
                "action_id": "question-1",
                "answer": [{"question": "风格", "answer": "正式"}],
            },
        ]

        with patch(
            "app.api.routers.agent_runtime.SessionRunner.resume_interrupt_batch",
            new=AsyncMock(return_value=None),
        ) as mock_resume:
            response = await client.post(
                f"/api/v1/agent/sessions/{session_id}/interrupt-resume",
                json={"batch_id": "batch-1", "responses": responses},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        await asyncio.sleep(0.05)
        mock_resume.assert_awaited_once_with("batch-1", responses)

    async def test_rollback_session_uses_revision_id_and_restores_data(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        buffer = get_agent_event_replay_buffer()
        buffer.clear_all()
        session.add(Project(id="proj-rollback", title="回滚项目"))
        session.add(
            Volume(
                id="vol-rollback",
                project_id="proj-rollback",
                title="第一卷",
                order=1,
                chapter_count=1,
            )
        )
        session.add(
            Chapter(
                id="chap-rollback",
                project_id="proj-rollback",
                volume_id="vol-rollback",
                title="第一章",
                content="旧内容",
                word_count=3,
                order=1,
            )
        )
        session.add(
            Task(
                id="task-rollback",
                project_id="proj-rollback",
                title="Agent Session",
                mode="agent",
                agent_session_id="sess-rollback",
            )
        )
        await session.commit()

        user_message = await message_repo.insert_message(
            session,
            session_id="sess-rollback",
            task_id="task-rollback",
            project_id="proj-rollback",
            role="user",
            status="sent",
            content="改写第一章",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-rollback",
            task_id="task-rollback",
            agent_session_id="sess-rollback",
            user_message_id=user_message.id,
            user_message_seq=user_message.seq,
            message="用户消息: 改写第一章",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-rollback",
        )
        session.add(
            RevisionChapterSnapshot(
                revision_id=revision.id,
                chapter_id="chap-rollback",
                project_id="proj-rollback",
                exists=True,
                title="第一章",
                content="旧内容",
                word_count=3,
                chapter_order=1,
            )
        )
        session.add(
            Commit(
                revision_id=revision.id,
                chapter_id="chap-rollback",
                operation="update",
                snapshot_title="第一章",
                snapshot_content="旧内容",
                snapshot_word_count=3,
                snapshot_order=1,
                new_title="第一章",
                new_content="新内容",
                new_word_count=3,
                new_order=1,
            )
        )
        chapter = await session.get(Chapter, "chap-rollback")
        assert chapter is not None
        chapter.content = "新内容"
        session.add(chapter)
        await message_repo.insert_message(
            session,
            session_id="sess-rollback",
            task_id="task-rollback",
            project_id="proj-rollback",
            role="assistant",
            status="complete",
            content="已改写",
        )
        child = await create_child_run(
            session,
            parent_session_id="sess-rollback",
            parent_task_id="task-rollback",
            parent_thread_id="sess-rollback",
            child_thread_id="sess-rollback:child:rollback",
            agent_key="writer",
            dispatch_id="dispatch-rollback",
            tool_call_id="tool-call-rollback",
            request={"task": "write", "input": {}, "metadata": {}},
            status="completed",
            parent_revision_id=revision.id,
            child_user_message_seq=0,
        )
        await session.commit()

        fake_runner = SimpleNamespace(
            cancel=MagicMock(),
            model_config={"max_context_tokens": 1},
            project_id="proj-rollback",
        )
        _SESSION_RUNNERS["sess-rollback"] = cast(Any, fake_runner)
        fake_registry = SimpleNamespace(cancel=AsyncMock())
        delete_checkpoints_after_mock = AsyncMock()
        delete_checkpoints_for_thread_mock = AsyncMock()
        emit_mock = AsyncMock()
        async with buffer.session_lock("sess-rollback"):
            buffer.record_unlocked(
                "agent:tool_call",
                {
                    "session_id": "sess-rollback",
                    "run_id": "rolled-back-run",
                    "tool_call_id": "rolled-back-tool",
                    "tool": "write_chapter",
                    "input": {"title": "不应重放"},
                },
            )

        with (
            patch(
                "app.api.routers.agent_runtime.get_agent_run_registry",
                return_value=fake_registry,
            ),
            patch(
                "app.api.routers.agent_runtime.delete_checkpoints_after_for_thread",
                delete_checkpoints_after_mock,
            ),
            patch(
                "app.api.routers.agent_runtime.delete_checkpoints_for_thread",
                delete_checkpoints_for_thread_mock,
            ),
            patch(
                "app.api.routers.agent_runtime.emit",
                new=emit_mock,
            ),
            patch(
                "app.agent_runtime.runner.subagent_runner.emit",
                new=emit_mock,
            ),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/sess-rollback/rollback",
                json={"revision_id": revision.id},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "restored_checkpoint_id" not in data
        assert data["restored_message_content"] == "改写第一章"
        assert data["affected_chapters"] == ["chap-rollback"]
        assert data["affected_world_entries"] == []
        assert data["revision_id"]
        emit_mock.assert_any_await(
            "agent:chapter_refresh",
            {
                "session_id": "sess-rollback",
                "project_id": "proj-rollback",
                "created_at": ANY,
                "chapter_id": "chap-rollback",
            },
            room=agent_session_room("sess-rollback"),
        )
        fake_runner.cancel.assert_called_once()
        fake_registry.cancel.assert_awaited_once_with("sess-rollback")
        delete_checkpoints_after_mock.assert_awaited_once_with(
            "sess-rollback", "cp-before"
        )
        delete_checkpoints_for_thread_mock.assert_awaited_once_with(child.child_thread_id)
        replayed = buffer.replay_events_unlocked("sess-rollback")
        assert all(event.name != "agent:tool_call" for event in replayed)
        rollback_statuses = [
            event.data
            for event in replayed
            if event.name == "agent:subagent_status"
            and event.data.get("child_run_id") == child.id
        ]
        assert rollback_statuses == [
            {
                "parent_session_id": "sess-rollback",
                "child_run_id": child.id,
                "child_thread_id": child.child_thread_id,
                "agent_key": "writer",
                "agent_number": child.metadata_json["agent_number"],
                "status": "cancelled",
                "queued_messages": 0,
                "is_active": False,
                "pending_approval": None,
            }
        ]
        emit_mock.assert_any_await(
            "agent:subagent_status",
            rollback_statuses[0],
            room=agent_subagents_room("sess-rollback"),
        )
        rolled_back_task = await session.get(Task, "task-rollback")
        assert rolled_back_task is not None
        await session.refresh(rolled_back_task)
        buffer.clear_all()

    async def test_rollback_created_chapter_emits_global_chapter_refresh_only(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        session.add(Project(id="proj-rollback-created", title="回滚新建章节项目"))
        session.add(
            Volume(
                id="vol-rollback-created",
                project_id="proj-rollback-created",
                title="第一卷",
                order=1,
                chapter_count=2,
            )
        )
        session.add(
            Chapter(
                id="chap-existing-rollback",
                project_id="proj-rollback-created",
                volume_id="vol-rollback-created",
                title="已有章节",
                content="已有内容",
                word_count=4,
                order=1,
            )
        )
        session.add(
            Task(
                id="task-rollback-created",
                project_id="proj-rollback-created",
                title="Agent Session",
                mode="agent",
                agent_session_id="sess-rollback-created",
            )
        )
        await session.commit()

        user_message = await message_repo.insert_message(
            session,
            session_id="sess-rollback-created",
            task_id="task-rollback-created",
            project_id="proj-rollback-created",
            role="user",
            status="sent",
            content="新建章节",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-rollback-created",
            task_id="task-rollback-created",
            agent_session_id="sess-rollback-created",
            user_message_id=user_message.id,
            user_message_seq=user_message.seq,
            message="用户消息: 新建章节",
            pre_run_checkpoint_id="cp-before-created",
            graph_thread_id="sess-rollback-created",
        )
        session.add(
            Chapter(
                id="chap-created-rollback",
                project_id="proj-rollback-created",
                volume_id="vol-rollback-created",
                title="新章节",
                content="新内容",
                word_count=3,
                order=2,
            )
        )
        session.add(
            RevisionChapterSnapshot(
                revision_id=revision.id,
                chapter_id="chap-created-rollback",
                project_id="proj-rollback-created",
                exists=False,
            )
        )
        await session.commit()

        fake_runner = SimpleNamespace(
            cancel=MagicMock(),
            model_config={"max_context_tokens": 1},
            project_id="proj-rollback-created",
        )
        _SESSION_RUNNERS["sess-rollback-created"] = cast(Any, fake_runner)
        fake_registry = SimpleNamespace(cancel=AsyncMock())
        emit_mock = AsyncMock()

        with (
            patch(
                "app.api.routers.agent_runtime.get_agent_run_registry",
                return_value=fake_registry,
            ),
            patch(
                "app.api.routers.agent_runtime.delete_checkpoints_after_for_thread",
                AsyncMock(),
            ),
            patch(
                "app.api.routers.agent_runtime.emit",
                new=emit_mock,
            ),
        ):
            response = await client.post(
                "/api/v1/agent/sessions/sess-rollback-created/rollback",
                json={"revision_id": revision.id},
            )

        assert response.status_code == status.HTTP_200_OK
        emit_mock.assert_any_await(
            "agent:chapter_refresh",
            {
                "session_id": "sess-rollback-created",
                "project_id": "proj-rollback-created",
                "created_at": ANY,
            },
            room=agent_session_room("sess-rollback-created"),
        )
        assert not any(
            call.args[0] == "agent:chapter_refresh"
            and call.args[1].get("chapter_id") == "chap-created-rollback"
            for call in emit_mock.await_args_list
        )
        volume = await session.get(Volume, "vol-rollback-created")
        assert volume is not None
        await session.refresh(volume)
        assert volume.chapter_count == 1

    async def test_rollback_rejects_checkpoint_id_request_body(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/api/v1/agent/sessions/sess-rollback/rollback",
            json={"checkpoint_id": "cp-before"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_fork_session_creates_task_runner_and_materializes_state(
        self,
        client: AsyncClient,
        session,
    ) -> None:
        session.add(Project(id="proj-fork", title="分叉项目"))
        session.add(
            Volume(
                id="vol-fork",
                project_id="proj-fork",
                title="第一卷",
                order=1,
                chapter_count=1,
            )
        )
        session.add(
            Chapter(
                id="chap-fork",
                project_id="proj-fork",
                volume_id="vol-fork",
                title="第一章",
                content="当前内容",
                word_count=4,
                order=1,
            )
        )
        session.add(
            Task(
                id="task-fork-source",
                project_id="proj-fork",
                title="Source Task",
                mode="agent",
                agent_session_id="sess-fork-source",
            )
        )
        await session.commit()

        user_message = await message_repo.insert_message(
            session,
            session_id="sess-fork-source",
            task_id="task-fork-source",
            project_id="proj-fork",
            role="user",
            status="sent",
            content="写第一轮",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-fork",
            task_id="task-fork-source",
            agent_session_id="sess-fork-source",
            user_message_id=user_message.id,
            user_message_seq=user_message.seq,
            message="用户消息: 写第一轮",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-fork-source",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-fork-source",
            task_id="task-fork-source",
            project_id="proj-fork",
            role="assistant",
            status="complete",
            content="第一轮完成",
        )
        await session.commit()

        with patch(
            "app.api.routers.agent_runtime._resolve_model_config",
            AsyncMock(
                return_value={
                    "max_context_tokens": 128000,
                    "reasoning_effort": "high",
                }
            ),
        ) as resolve_model_config, patch(
            "app.agent_runtime.runner.session_runner.SessionRunner.materialize_state",
            AsyncMock(return_value="fork-cp"),
        ) as materialize_state:
            response = await client.post(
                "/api/v1/agent/sessions/sess-fork-source/fork",
                json={
                    "source_revision_id": revision.id,
                    "model_id": "model-fork",
                    "reasoning_effort": "high",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] in _SESSION_RUNNERS
        assert data["task_title"] == "Source Task(Fork)"
        materialize_state.assert_awaited_once()
        assert materialize_state.await_args is not None
        state_values = materialize_state.await_args.args[0]
        assert state_values["session_id"] == data["session_id"]
        assert state_values["current_revision_id"] is None
        assert state_values["model_config"]["reasoning_effort"] == "high"
        resolve_model_config.assert_awaited_once_with(session, "model-fork", "high")
        fork_task = await session.get(Task, data["task_id"])
        assert fork_task is not None
