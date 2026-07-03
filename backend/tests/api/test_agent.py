# -*- coding: utf-8 -*-
"""Agent API 测试。"""

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient

from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.child_runs import (
    count_pending_child_run_requests,
    create_child_run,
    record_child_run_pending_approval,
)
from app.agent_runtime.revisions import begin_user_revision
from app.agent_runtime.runner.checkpointer import reset_checkpointer
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.api.routers.agent_runtime import _SESSION_RUNNERS
from app.socket.handlers import agent_subagents_room
from app.storage.models.chapter import Chapter
from app.storage.models.commit import Commit
from app.storage.models.project import Project
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from app.storage.services import task_service


@pytest_asyncio.fixture(autouse=True)
async def reset_agent_runtime_globals():
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
        "model_id": model_id,
    }


@pytest.mark.asyncio
class TestAgentAPI:
    async def test_list_agent_tools_success(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/agent/tools")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "key": "ask_user",
                "name": "Ask",
                "description": "向用户提问以获取继续执行所需的信息。",
                "is_readonly": True,
            },
            {
                "key": "get_plan",
                "name": "Get Plan",
                "description": "读取指定共享计划及其 Todo 列表。",
                "is_readonly": True,
            },
            {
                "key": "list_plan",
                "name": "List Plans",
                "description": "列出当前父子会话共享的全部计划。",
                "is_readonly": True,
            },
            {
                "key": "create_plan",
                "name": "Create Plan",
                "description": "创建一个共享计划并初始化 Todo 列表。",
                "is_readonly": False,
            },
            {
                "key": "update_plan",
                "name": "Update Plan",
                "description": "按旧 Todo 切片精确替换共享计划中的 Todo 列表。",
                "is_readonly": False,
            },
            {
                "key": "read_chapter",
                "name": "Read",
                "description": "读取指定章节内容供 Agent 参考。",
                "is_readonly": True,
            },
            {
                "key": "list_chapters",
                "name": "List",
                "description": "列出指定卷内章节供 Agent 定位上下文。",
                "is_readonly": True,
            },
            {
                "key": "list_volumes",
                "name": "List Volumes",
                "description": "列出项目卷信息供 Agent 定位章节。",
                "is_readonly": True,
            },
            {
                "key": "write_chapter",
                "name": "Write",
                "description": "在指定卷内创建章节。",
                "is_readonly": False,
            },
            {
                "key": "edit_chapter",
                "name": "Edit",
                "description": "精确替换现有章节的标题或正文片段。",
                "is_readonly": False,
            },
            {
                "key": "delete_chapter",
                "name": "Delete",
                "description": "删除指定章节。",
                "is_readonly": False,
            },
            {
                "key": "create_volume",
                "name": "Create Volume",
                "description": "在项目末尾创建新卷。",
                "is_readonly": False,
            },
            {
                "key": "edit_volume",
                "name": "Edit Volume",
                "description": "编辑指定卷的标题或说明。",
                "is_readonly": False,
            },
            {
                "key": "delete_volume",
                "name": "Delete Volume",
                "description": "删除指定卷。",
                "is_readonly": False,
            },
            {
                "key": "move_chapter_to_volume",
                "name": "Move Chapter",
                "description": "将指定章节移动到目标卷末尾。",
                "is_readonly": False,
            },
            {
                "key": "list_world_entries",
                "name": "List World Entries",
                "description": "列出当前项目世界书条目标题。",
                "is_readonly": True,
            },
            {
                "key": "read_world_entry",
                "name": "Read World Entry",
                "description": "根据标题读取世界书条目内容。",
                "is_readonly": True,
            },
            {
                "key": "create_world_entry",
                "name": "Create World Entry",
                "description": "在当前项目世界书中创建条目。",
                "is_readonly": False,
            },
            {
                "key": "edit_world_entry",
                "name": "Edit World Entry",
                "description": "编辑世界书条目的标题或内容。",
                "is_readonly": False,
            },
            {
                "key": "delete_world_entry",
                "name": "Delete World Entry",
                "description": "删除指定世界书条目。",
                "is_readonly": False,
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
                "agent_key": "primary",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent_key"] == "primary"
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
        assert data["agent_key"] == "primary"

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
                "key": "primary",
                "display_name": "Primary Agent",
                "kind": "primary",
                "prompt_agent_name": "primary",
                "tool_category_keys": ["orchestration", "interaction", "chapter_read"],
                "enabled_skill_ids": [],
                "metadata": {},
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED

        resp = await client.put(
            "/api/v1/agent-definitions/primary",
            json={"enabled": False},
        )
        assert resp.status_code == status.HTTP_200_OK

        response = await client.post(
            "/api/v1/agent/sessions",
            json={
                "project_id": target["project_id"],
                "model_id": target["model_id"],
                "max_iterations": 5,
                "agent_key": "primary",
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
                "prompt_agent_name": "primary",
                "tool_category_keys": ["orchestration", "interaction", "chapter_read"],
                "enabled_skill_ids": [],
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

        class FakeGraph:
            async def aget_state(self, config):
                return SimpleNamespace(values={"session_id": session_id})

        fake_registry = SimpleNamespace(is_running=AsyncMock(return_value=True))

        with patch.object(
            _SESSION_RUNNERS[session_id],
            "_get_graph",
            AsyncMock(return_value=FakeGraph()),
        ), patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ):
            response = await client.get(f"/api/v1/agent/sessions/{session_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == session_id
        assert data["state"] == {"session_id": session_id}
        assert data["is_running"] is True
        fake_registry.is_running.assert_awaited_once_with(session_id)

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

        class FakeGraph:
            async def aget_state(self, config):
                return SimpleNamespace(
                    next=("primary",),
                    values={"current_revision_id": revision.id},
                    config={"configurable": {}},
                )

        fake_registry = SimpleNamespace(
            cancel=AsyncMock(return_value=True),
            register=AsyncMock(),
            unregister=AsyncMock(return_value=True),
            is_running=AsyncMock(return_value=False),
            is_parent_running=AsyncMock(return_value=False),
        )
        runner = _SESSION_RUNNERS[session_id]

        with patch.object(
            runner,
            "_get_graph",
            AsyncMock(return_value=FakeGraph()),
        ), patch(
            "app.storage.repos.revision_repo.get_by_id",
            AsyncMock(return_value=SimpleNamespace(id=revision.id, status="cancelled")),
        ), patch(
            "app.api.routers.agent_runtime.get_agent_run_registry",
            return_value=fake_registry,
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.continue_with_user_message",
            new=AsyncMock(return_value=None),
        ) as mock_continue, patch(
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
        mock_continue.assert_not_awaited()
        mock_run.assert_awaited_once_with(user_request="取消上一轮后重新开始")

    async def test_get_session_state_rehydrates_persisted_session_without_runner(
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
        assert session_id in _SESSION_RUNNERS

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

    async def test_send_message_continues_unfinished_graph_without_restarting(
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

        class FakeGraph:
            async def aget_state(self, config):
                return SimpleNamespace(
                    next=("primary",),
                    values={"current_revision_id": "rev-existing"},
                )

        with patch.object(
            _SESSION_RUNNERS[session_id],
            "_get_graph",
            AsyncMock(return_value=FakeGraph()),
        ), patch(
            "app.storage.repos.revision_repo.get_by_id",
            AsyncMock(return_value=SimpleNamespace(status="interrupted")),
        ), patch(
            "app.api.routers.agent_runtime.SessionRunner.continue_with_user_message",
            new=AsyncMock(return_value=None),
        ) as mock_continue, patch(
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
        mock_continue.assert_awaited_once_with("根据当前审核继续处理")
        mock_run.assert_not_awaited()

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
        fake_registry = SimpleNamespace(is_running=AsyncMock(return_value=True))

        with patch.object(
            runner,
            "can_continue",
            AsyncMock(return_value=False),
        ), patch.object(
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
            "app.api.routers.agent_runtime.SessionRunner.continue_with_user_message",
            new=AsyncMock(return_value=None),
        ) as mock_continue, patch(
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
        mock_continue.assert_not_awaited()
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
                json={"action_id": "question-1", "answer": "回答澄清问题"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True
            await asyncio.sleep(0.05)
            mock_resume.assert_awaited_once_with({
                "action_type": "clarification",
                "action_id": "question-1",
                "answer": "回答澄清问题",
            })

    async def test_rollback_session_uses_revision_id_and_restores_data(
        self,
        client: AsyncClient,
        session,
    ) -> None:
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
        await session.commit()

        fake_runner = SimpleNamespace(
            cancel=MagicMock(),
        )
        _SESSION_RUNNERS["sess-rollback"] = cast(Any, fake_runner)
        fake_registry = SimpleNamespace(cancel=AsyncMock())
        delete_checkpoints_after_mock = AsyncMock()

        with (
            patch(
                "app.api.routers.agent_runtime.get_agent_run_registry",
                return_value=fake_registry,
            ),
            patch(
                "app.api.routers.agent_runtime.delete_checkpoints_after_for_thread",
                delete_checkpoints_after_mock,
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
        assert data["revision_id"]
        fake_runner.cancel.assert_called_once()
        fake_registry.cancel.assert_awaited_once_with("sess-rollback")
        delete_checkpoints_after_mock.assert_awaited_once_with(
            "sess-rollback", "cp-before"
        )
        rolled_back_task = await session.get(Task, "task-rollback")
        assert rolled_back_task is not None
        await session.refresh(rolled_back_task)

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
            AsyncMock(return_value={"max_context_tokens": 128000}),
        ), patch(
            "app.agent_runtime.runner.session_runner.SessionRunner.materialize_state",
            AsyncMock(return_value="fork-cp"),
        ) as materialize_state:
            response = await client.post(
                "/api/v1/agent/sessions/sess-fork-source/fork",
                json={"source_revision_id": revision.id, "model_id": "model-fork"},
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
        fork_task = await session.get(Task, data["task_id"])
        assert fork_task is not None
