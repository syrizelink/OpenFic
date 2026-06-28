# -*- coding: utf-8 -*-
"""Task API contract tests for agent-runtime backed tasks."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.modes import AgentMode
from app.agent_runtime.persistence import repo as agent_run_repo
from app.storage.services import task_service


@pytest.mark.asyncio
class TestTaskAPI:
    async def create_project_and_chapter(self, client: AsyncClient) -> tuple[str, str]:
        project_response = await client.post("/api/v1/projects", data={"title": "测试项目"})
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]
        volumes_response = await client.get(f"/api/v1/projects/{project_id}/volumes")
        assert volumes_response.status_code == status.HTTP_200_OK
        volume_id = volumes_response.json()[0]["id"]

        chapter_response = await client.post(
            f"/api/v1/projects/{project_id}/chapters",
            json={
                "volume_id": volume_id,
                "title": "测试章节",
                "content": "测试内容",
            },
        )
        assert chapter_response.status_code == status.HTTP_201_CREATED
        chapter_id = chapter_response.json()["id"]
        return project_id, chapter_id

    async def create_agent_task(
        self,
        client: AsyncClient,
        session: AsyncSession,
        *,
        title: str = "Agent 任务",
        session_id: str | None = "session-task-api",
        mode: AgentMode = "agent",
    ):
        project_id, chapter_id = await self.create_project_and_chapter(client)
        task = await task_service.create_task(
            session,
            project_id=project_id,
            title=title,
            mode=mode,
            agent_session_id=session_id,
        )
        await session.commit()
        return task, project_id, chapter_id

    async def test_create_task_endpoint_is_removed(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "project_id": "project",
                "chapter_id": "chapter",
                "title": "legacy chat",
                "mode": "chat",
                "messages": [],
            },
        )

        assert response.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED}

    async def test_get_task_uses_agent_runtime_projection_with_agent_mode(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, project_id, _chapter_id = await self.create_agent_task(client, session)
        await agent_run_repo.insert_message(
            session,
            session_id=task.agent_session_id or "",
            task_id=task.id,
            project_id=project_id,
            role="user",
            content="续写一段剧情",
            status="sent",
            metadata={"revision_id": "rev-task"},
        )
        await session.commit()

        response = await client.get(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] == "agent"
        assert data["id"] == task.id
        assert data["agent_session_id"] == task.agent_session_id
        assert data["messages"][0]["content"] == "续写一段剧情"
        assert data["messages"][0]["payload"] == {
            "kind": "user_request",
            "revision_id": "rev-task",
        }
        legacy_message_fields = {
            "event_type",
            "event_data",
            "checkpoint_id",
            "revision_id",
            "commit_ids",
            "is_checkpoint",
        }
        assert legacy_message_fields.isdisjoint(data["messages"][0])

    async def test_get_task_returns_persisted_token_usage(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)
        task.token_input = 123
        task.token_output = 45
        task.token_cache = 6
        task.context_input_tokens = 78
        await session.commit()

        response = await client.get(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["token_input"] == 123
        assert data["token_output"] == 45
        assert data["token_cache"] == 6
        assert data["context_input_tokens"] == 78

    async def test_get_task_returns_persisted_running_state(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)
        task.is_running = True
        await session.commit()

        response = await client.get(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_running"] is True

    async def test_get_task_without_agent_session_returns_empty_messages(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(
            client,
            session,
            session_id=None,
        )

        response = await client.get(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] == "agent"
        assert data["messages"] == []
        assert "context_anchor" not in data

    async def test_list_tasks_has_agent_mode_field(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, project_id, chapter_id = await self.create_agent_task(client, session, title="任务 1")
        await task_service.create_task(
            session,
            project_id=project_id,
            title="任务 2",
            mode="agent",
            agent_session_id="session-task-api-2",
        )
        await session.commit()

        response = await client.get(f"/api/v1/projects/{project_id}/tasks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 2
        assert all(item["mode"] == "agent" for item in data["items"])
        assert {item["id"] for item in data["items"]} >= {task.id}

    async def test_list_tasks_returns_running_state(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, project_id, _chapter_id = await self.create_agent_task(client, session, title="任务 1")
        task.is_running = True
        await session.commit()

        response = await client.get(f"/api/v1/projects/{project_id}/tasks")

        assert response.status_code == status.HTTP_200_OK
        items = {item["id"]: item for item in response.json()["items"]}
        assert items[task.id]["is_running"] is True

    async def test_list_tasks_rejects_removed_mode_query(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        _task, project_id, chapter_id = await self.create_agent_task(client, session, title="任务 1")
        await task_service.create_task(
            session,
            project_id=project_id,
            title="任务 2",
            mode="agent",
            agent_session_id="session-task-api-2",
        )
        await session.commit()

        response = await client.get(f"/api/v1/projects/{project_id}/tasks?mode=legacy")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_update_task_does_not_accept_messages(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)

        response = await client.patch(
            f"/api/v1/tasks/{task.id}",
            json={"messages": [], "title": "新标题"},
        )

        assert response.status_code == 422

    async def test_update_task_metadata(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)

        response = await client.patch(
            f"/api/v1/tasks/{task.id}",
            json={"title": "新标题", "is_favorited": True},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["mode"] == "agent"
        assert data["title"] == "新标题"
        assert data["is_favorited"] is True
        assert data["messages"] == []
        assert "context_anchor" not in data

    async def test_delete_task(self, client: AsyncClient, session: AsyncSession) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)

        with patch(
            "app.api.routers.tasks.delete_checkpoints_for_thread",
            new=AsyncMock(return_value=2),
        ) as delete_checkpoints:
            response = await client.delete(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_checkpoints.assert_awaited_once_with(task.agent_session_id)

        get_response = await client.get(f"/api/v1/tasks/{task.id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_task_rejects_running_task(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)
        task.is_running = True
        await session.commit()

        with patch(
            "app.api.routers.tasks.delete_checkpoints_for_thread",
            new=AsyncMock(return_value=0),
        ) as delete_checkpoints:
            response = await client.delete(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "任务运行中，不能删除"
        delete_checkpoints.assert_not_awaited()

        get_response = await client.get(f"/api/v1/tasks/{task.id}")
        assert get_response.status_code == status.HTTP_200_OK

    async def test_delete_all_tasks_skips_running_tasks(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        running_task, project_id, chapter_id = await self.create_agent_task(
            client,
            session,
            title="运行中任务",
            session_id="session-running",
        )
        running_task.is_running = True
        idle_task = await task_service.create_task(
            session,
            project_id=project_id,
            title="已停止任务",
            mode="agent",
            agent_session_id="session-idle",
        )
        await session.commit()

        with patch(
            "app.api.routers.tasks.delete_checkpoints_for_thread",
            new=AsyncMock(return_value=2),
        ) as delete_checkpoints:
            response = await client.delete(f"/api/v1/projects/{project_id}/tasks")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "deleted_count": 1,
            "skipped_running_count": 1,
        }
        delete_checkpoints.assert_awaited_once_with(idle_task.agent_session_id)

        running_response = await client.get(f"/api/v1/tasks/{running_task.id}")
        idle_response = await client.get(f"/api/v1/tasks/{idle_task.id}")
        assert running_response.status_code == status.HTTP_200_OK
        assert idle_response.status_code == status.HTTP_404_NOT_FOUND
