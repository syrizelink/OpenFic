# -*- coding: utf-8 -*-
"""
Project API 测试。
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agent_runtime.persistence import repo as agent_run_repo
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentRunMessage,
    PlanRecord,
    PlanTodoRecord,
)
from app.storage.models.task import Task
from app.storage.models.task_message import TaskMessage
from app.storage.services import task_service


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    """测试创建项目。"""
    response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说", "description": "这是一个测试小说"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "测试小说"
    assert data["description"] == "这是一个测试小说"
    assert data["word_count"] == 0
    assert data["chapter_count"] == 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_project_without_description(client: AsyncClient) -> None:
    """测试创建不带简介的项目。"""
    response = await client.post(
        "/api/v1/projects",
        data={"title": "无简介小说"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "无简介小说"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_project_empty_title(client: AsyncClient) -> None:
    """测试创建项目时标题为空。"""
    response = await client.post(
        "/api/v1/projects",
        data={"title": ""},
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient) -> None:
    """测试获取空的项目列表。"""
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    """测试获取项目列表。"""
    # 创建几个项目
    for i in range(3):
        await client.post(
            "/api/v1/projects",
            data={"title": f"小说 {i + 1}"},
        )

    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_projects_pagination(client: AsyncClient) -> None:
    """测试项目列表分页。"""
    # 创建 5 个项目
    for i in range(5):
        await client.post(
            "/api/v1/projects",
            data={"title": f"小说 {i + 1}"},
        )

    # 获取第一页
    response = await client.get("/api/v1/projects?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2

    # 获取第二页
    response = await client.get("/api/v1/projects?page=2&page_size=2")
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_list_projects_search_and_sort(client: AsyncClient) -> None:
    """测试项目列表的服务端搜索和排序。"""
    await client.post(
        "/api/v1/projects",
        data={"title": "Zeta 项目", "description": "包含目标词"},
    )
    await client.post(
        "/api/v1/projects",
        data={"title": "Alpha 项目", "description": "普通简介"},
    )
    await client.post(
        "/api/v1/projects",
        data={"title": "Beta 项目", "description": "另一个目标词"},
    )

    search_response = await client.get(
        "/api/v1/projects?search=目标词&page=1&page_size=1",
    )
    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data["total"] == 2
    assert len(search_data["items"]) == 1

    sort_response = await client.get(
        "/api/v1/projects?sort_by=title&sort_order=asc&page_size=100",
    )
    assert sort_response.status_code == 200
    assert [item["title"] for item in sort_response.json()["items"]] == [
        "Alpha 项目",
        "Beta 项目",
        "Zeta 项目",
    ]


@pytest.mark.asyncio
async def test_list_projects_supports_pinyin_search_and_sort(client: AsyncClient) -> None:
    """拼音搜索和标题排序应保持与旧客户端一致。"""
    await client.post("/api/v1/projects", data={"title": "中篇项目"})
    await client.post("/api/v1/projects", data={"title": "红星项目", "description": "银河故事"})
    await client.post("/api/v1/projects", data={"title": "阿尔法项目"})

    search_response = await client.get("/api/v1/projects?search=hxxm")
    assert search_response.status_code == 200
    assert [item["title"] for item in search_response.json()["items"]] == ["红星项目"]

    sort_response = await client.get(
        "/api/v1/projects?sort_by=title&sort_order=asc&page_size=100",
    )
    assert sort_response.status_code == 200
    assert [item["title"] for item in sort_response.json()["items"]] == [
        "阿尔法项目",
        "红星项目",
        "中篇项目",
    ]


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient) -> None:
    """测试获取项目详情。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说", "description": "测试简介"},
    )
    project_id = create_response.json()["id"]

    # 获取项目
    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["title"] == "测试小说"
    assert data["description"] == "测试简介"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """测试获取不存在的项目。"""
    response = await client.get("/api/v1/projects/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    """测试更新项目。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "原标题", "description": "原简介"},
    )
    project_id = create_response.json()["id"]

    # 更新项目
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        data={"title": "新标题", "description": "新简介"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "新标题"
    assert data["description"] == "新简介"


@pytest.mark.asyncio
async def test_update_project_partial(client: AsyncClient) -> None:
    """测试部分更新项目。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "原标题", "description": "原简介"},
    )
    project_id = create_response.json()["id"]

    # 只更新标题
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        data={"title": "新标题"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "新标题"
    assert data["description"] == "原简介"  # 简介保持不变


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient) -> None:
    """测试更新不存在的项目。"""
    response = await client.patch(
        "/api/v1/projects/nonexistent",
        data={"title": "新标题"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """测试删除项目。"""
    # 创建项目
    create_response = await client.post(
        "/api/v1/projects",
        data={"title": "待删除小说"},
    )
    project_id = create_response.json()["id"]

    # 删除项目
    response = await client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204

    # 确认已删除
    get_response = await client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_deletes_tasks_and_runtime_data(client, session) -> None:
    create_response = await client.post("/api/v1/projects", data={"title": "待删除项目"})
    project_id = create_response.json()["id"]
    task = await task_service.create_task(
        session,
        project_id=project_id,
        title="待删除任务",
        mode="agent",
        agent_session_id="project-delete-session",
    )
    await create_child_run(
        session,
        parent_session_id="project-delete-session",
        parent_task_id=task.id,
        parent_thread_id="project-delete-session",
        child_thread_id="project-delete-session:child:writer",
        agent_key="writer",
        dispatch_id="writer",
        tool_call_id="tool-writer",
        request={"task": "write", "input": {}, "metadata": {}},
    )
    await agent_run_repo.insert_message(
        session,
        session_id="project-delete-session",
        task_id=task.id,
        project_id=project_id,
        role="assistant",
        content="runtime message",
        status="completed",
    )
    session.add(
        TaskMessage(
            id="project-delete-message",
            task_id=task.id,
            role="assistant",
            content="legacy runtime message",
            tool_calls="[]",
            message_metadata="{}",
        )
    )
    session.add_all(
        [
            AgentContextCompaction(
                session_id="project-delete-session",
                task_id=task.id,
                project_id=project_id,
                start_seq=0,
                end_seq=1,
                summary="runtime summary",
                trigger="manual",
            ),
            PlanRecord(id="project-delete-plan", session_id="project-delete-session"),
            PlanTodoRecord(
                id="project-delete-todo",
                plan_id="project-delete-plan",
                content="runtime todo",
                sort_index=0,
            ),
        ]
    )
    await session.commit()

    with patch(
        "app.api.routers.projects.delete_checkpoints_for_thread",
        new=AsyncMock(return_value=0),
    ) as delete_checkpoints:
        response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 204
    assert delete_checkpoints.await_count == 2
    for model in (
        Task,
        TaskMessage,
        AgentRunMessage,
        AgentChildRun,
        AgentChildRunRequest,
        AgentContextCompaction,
        PlanRecord,
        PlanTodoRecord,
    ):
        result = await session.execute(select(model))
        assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_project_rejects_running_tasks(client, session) -> None:
    create_response = await client.post("/api/v1/projects", data={"title": "运行中项目"})
    project_id = create_response.json()["id"]
    task = await task_service.create_task(
        session,
        project_id=project_id,
        title="运行中任务",
        mode="agent",
        agent_session_id="running-project-session",
    )
    task.is_running = True
    await session.commit()

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "项目存在运行中任务，不能删除"


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    """测试删除不存在的项目。"""
    response = await client.delete("/api/v1/projects/nonexistent")
    assert response.status_code == 404
