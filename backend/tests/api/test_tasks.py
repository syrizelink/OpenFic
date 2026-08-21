# -*- coding: utf-8 -*-
"""Task API contract tests for agent-runtime backed tasks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.modes import AgentMode
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence import repo as agent_run_repo
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentRunMessage,
    PlanRecord,
    PlanTodoRecord,
)
from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.models.revision import Revision
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
        task.cost = 0.28
        await session.commit()

        response = await client.get(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["token_input"] == 123
        assert data["token_output"] == 45
        assert data["token_cache"] == 6
        assert data["context_input_tokens"] == 78
        assert data["cost"] == 0.28

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

    async def test_list_tasks_treats_pending_interrupt_as_running(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, project_id, _chapter_id = await self.create_agent_task(
            client,
            session,
            title="等待用户输入的任务",
        )
        task.is_running = False
        await session.commit()

        fake_checkpointer = AsyncMock()
        fake_checkpointer.aget_tuple.return_value = SimpleNamespace(
            pending_writes=[
                (
                    "task-write",
                    "__interrupt__",
                    [SimpleNamespace(value={"type": "ask_user"})],
                )
            ]
        )
        with patch(
            "app.api.routers.tasks.get_checkpointer",
            new=AsyncMock(return_value=fake_checkpointer),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/tasks")

        assert response.status_code == status.HTTP_200_OK
        items = {item["id"]: item for item in response.json()["items"]}
        assert items[task.id]["is_running"] is True

    async def test_list_tasks_ignores_pending_interrupt_for_cancelled_revision(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, project_id, _chapter_id = await self.create_agent_task(
            client,
            session,
            title="宸插彇娑堢殑浠诲姟",
        )
        revision = Revision(
            project_id=task.project_id,
            task_id=task.id,
            message="cancelled approval",
            agent_session_id=task.agent_session_id,
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
        task.is_running = False
        session.add(task)
        await session.commit()

        fake_checkpointer = AsyncMock()
        fake_checkpointer.aget_tuple.return_value = SimpleNamespace(
            pending_writes=[
                (
                    "task-write",
                    "__interrupt__",
                    [SimpleNamespace(value={"type": "tool_approval"})],
                )
            ]
        )
        with patch(
            "app.api.routers.tasks.get_checkpointer",
            new=AsyncMock(return_value=fake_checkpointer),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/tasks")

        assert response.status_code == status.HTTP_200_OK
        items = {item["id"]: item for item in response.json()["items"]}
        assert items[task.id]["is_running"] is False

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
            with patch(
                "app.api.routers.tasks.delete_attachments_for_task",
                new=AsyncMock(return_value=1),
            ) as delete_attachments:
                response = await client.delete(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_checkpoints.assert_awaited_once_with(task.agent_session_id)
        delete_attachments.assert_awaited_once_with(session, task_id=task.id)

        get_response = await client.get(f"/api/v1/tasks/{task.id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_task_cleans_runtime_data_but_keeps_audit_logs(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, project_id, _chapter_id = await self.create_agent_task(client, session)
        await create_child_run(
            session,
            parent_session_id=task.agent_session_id or "",
            parent_task_id=task.id,
            parent_thread_id=task.agent_session_id or "",
            child_thread_id="session-task-api:child:writer",
            agent_key="writer",
            dispatch_id="writer",
            tool_call_id="tool-writer",
            request={"task": "write", "input": {}, "metadata": {}},
        )
        await agent_run_repo.insert_message(
            session,
            session_id=task.agent_session_id or "",
            task_id=task.id,
            project_id=project_id,
            role="assistant",
            content="runtime message",
            status="completed",
        )
        session.add_all(
            [
                AgentContextCompaction(
                    session_id=task.agent_session_id or "",
                    task_id=task.id,
                    project_id=project_id,
                    start_seq=0,
                    end_seq=1,
                    summary="runtime summary",
                    trigger="manual",
                ),
                PlanRecord(id="plan-task", session_id=task.agent_session_id or ""),
                PlanTodoRecord(
                    id="todo-task",
                    plan_id="plan-task",
                    content="runtime todo",
                    sort_index=0,
                ),
                LLMAuditLog(
                    id="audit-task",
                    task_id=task.id,
                    session_id=task.agent_session_id,
                    project_id=project_id,
                    operation="build",
                    model_id="test-model",
                    status="success",
                ),
            ]
        )
        await session.commit()

        with patch(
            "app.api.routers.tasks.delete_checkpoints_for_thread",
            new=AsyncMock(return_value=0),
        ):
            response = await client.delete(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        for model in (
            AgentRunMessage,
            AgentChildRun,
            AgentChildRunRequest,
            AgentContextCompaction,
            PlanRecord,
            PlanTodoRecord,
        ):
            result = await session.execute(select(model))
            assert result.scalars().all() == []
        audit_result = await session.execute(
            select(LLMAuditLog).where(LLMAuditLog.id == "audit-task")
        )
        assert audit_result.scalar_one_or_none() is not None

    async def test_delete_task_deletes_descendant_subagent_checkpoints(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ) -> None:
        task, _project_id, _chapter_id = await self.create_agent_task(client, session)
        parent_session_id = task.agent_session_id or ""
        child = await create_child_run(
            session,
            parent_session_id=parent_session_id,
            parent_task_id=task.id,
            parent_thread_id=parent_session_id,
            child_thread_id=f"{parent_session_id}:child:writer",
            agent_key="writer",
            dispatch_id="dispatch-writer",
            tool_call_id="tool-call-writer",
            request={"task": "write", "input": {}, "metadata": {}},
        )
        grandchild = await create_child_run(
            session,
            parent_session_id=child.child_thread_id,
            parent_task_id=task.id,
            parent_thread_id=child.child_thread_id,
            child_thread_id=f"{child.child_thread_id}:child:reviewer",
            agent_key="reviewer",
            dispatch_id="dispatch-reviewer",
            tool_call_id="tool-call-reviewer",
            request={"task": "review", "input": {}, "metadata": {}},
        )
        await session.commit()

        with patch(
            "app.api.routers.tasks.delete_checkpoints_for_thread",
            new=AsyncMock(return_value=2),
        ) as delete_checkpoints:
            response = await client.delete(f"/api/v1/tasks/{task.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert delete_checkpoints.await_args_list == [
            ((grandchild.child_thread_id,), {}),
            ((child.child_thread_id,), {}),
            ((parent_session_id,), {}),
        ]

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
        await agent_run_repo.insert_message(
            session,
            session_id="session-idle",
            task_id=idle_task.id,
            project_id=project_id,
            role="assistant",
            content="idle runtime message",
            status="completed",
        )
        await create_child_run(
            session,
            parent_session_id="session-idle",
            parent_task_id=idle_task.id,
            parent_thread_id="session-idle",
            child_thread_id="session-idle:child:writer",
            agent_key="writer",
            dispatch_id="idle-writer",
            tool_call_id="idle-tool-writer",
            request={"task": "write", "input": {}, "metadata": {}},
        )
        session.add_all(
            [
                AgentContextCompaction(
                    session_id="session-idle",
                    task_id=idle_task.id,
                    project_id=project_id,
                    start_seq=0,
                    end_seq=1,
                    summary="idle summary",
                    trigger="manual",
                ),
                PlanRecord(id="idle-plan", session_id="session-idle"),
                PlanTodoRecord(
                    id="idle-todo",
                    plan_id="idle-plan",
                    content="idle todo",
                    sort_index=0,
                ),
            ]
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
        assert delete_checkpoints.await_args_list == [
            (("session-idle:child:writer",), {}),
            ((idle_task.agent_session_id,), {}),
        ]

        running_response = await client.get(f"/api/v1/tasks/{running_task.id}")
        idle_response = await client.get(f"/api/v1/tasks/{idle_task.id}")
        assert running_response.status_code == status.HTTP_200_OK
        assert idle_response.status_code == status.HTTP_404_NOT_FOUND
        for model in (
            AgentRunMessage,
            AgentChildRun,
            AgentChildRunRequest,
            AgentContextCompaction,
            PlanRecord,
            PlanTodoRecord,
        ):
            result = await session.execute(select(model))
            assert result.scalars().all() == []
