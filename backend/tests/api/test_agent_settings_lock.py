# -*- coding: utf-8 -*-

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from unittest.mock import MagicMock

from app.agent_runtime.persistence.child_runs import create_child_run
from app.api.routers.agent_runtime import _SESSION_RUNNERS
from app.storage.models.revision import Revision
from app.storage.models.task import Task


async def _create_agent_task(
    client: AsyncClient,
    session: AsyncSession,
    *,
    is_running: bool = False,
) -> Task:
    project_response = await client.post("/api/v1/projects", data={"title": "锁定设置测试"})
    assert project_response.status_code == 201

    task = Task(
        project_id=project_response.json()["id"],
        title="Agent settings lock",
        mode="agent",
        agent_session_id="agent-settings-lock-test",
        is_running=is_running,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


@pytest.mark.asyncio
async def test_agent_settings_lock_reports_running_agent_task(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_agent_task(client, session, is_running=True)

    response = await client.get("/api/v1/settings/agent-session-lock")

    assert response.status_code == 200
    assert response.json() == {"is_locked": True}


@pytest.mark.asyncio
async def test_agent_settings_lock_ignores_interrupted_parent_session(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    task = await _create_agent_task(client, session)
    revision = Revision(
        project_id=task.project_id,
        task_id=task.id,
        message="已暂停的会话不应锁定设置",
        agent_session_id=task.agent_session_id,
        revision_type="agent",
        status="interrupted",
        is_checkpoint=True,
        project_snapshot_title="锁定设置测试",
        project_snapshot_word_count=0,
        project_snapshot_chapter_count=0,
    )
    session.add(revision)
    await session.flush()
    task.current_revision_id = revision.id
    session.add(task)
    await session.commit()

    response = await client.get("/api/v1/settings/agent-session-lock")

    assert response.status_code == 200
    assert response.json() == {"is_locked": False}


@pytest.mark.asyncio
async def test_agent_settings_lock_reports_waiting_subagent(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    task = await _create_agent_task(client, session)
    await create_child_run(
        session,
        parent_session_id=task.agent_session_id or "",
        parent_task_id=task.id,
        parent_thread_id=task.agent_session_id or "",
        child_thread_id="agent-settings-lock-test:child",
        agent_key="writer",
        dispatch_id="dispatch-settings-lock",
        tool_call_id="tool-call-settings-lock",
        request={"task": "等待工具审批"},
        status="waiting_user",
    )

    response = await client.get("/api/v1/settings/agent-session-lock")

    assert response.status_code == 200
    assert response.json() == {"is_locked": True}


@pytest.mark.asyncio
async def test_agent_settings_lock_is_clear_without_active_session(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/agent-session-lock")

    assert response.status_code == 200
    assert response.json() == {"is_locked": False}


@pytest.mark.asyncio
async def test_agent_settings_lock_rejects_restricted_writes(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_agent_task(client, session, is_running=True)

    restricted_response = await client.put(
        "/api/v1/settings",
        json={"index_mode": "all"},
    )
    provider_response = await client.post(
        "/api/v1/model-providers",
        data={
            "name": "Locked provider",
            "url": "https://api.example.com",
            "api_key": "test-key",
            "provider_type": "openai",
        },
    )
    model_response = await client.post(
        "/api/v1/models",
        json={
            "name": "Locked model",
            "provider_id": "provider-id",
            "model_id": "locked-model",
        },
    )
    rule_response = await client.post(
        "/api/v1/agent-rules",
        json={"title": "Locked rule", "content": "Blocked while running"},
    )
    skill_response = await client.post(
        "/api/v1/skills",
        json={"name": "Locked skill", "summary": "", "content": ""},
    )
    definition_response = await client.post(
        "/api/v1/agent-definitions",
        json={
            "key": "locked-agent",
            "display_name": "Locked Agent",
            "kind": "subagent",
            "prompt_agent_name": "locked-agent",
            "enabled_tool_categories": [],
            "enabled_skills": [],
        },
    )

    for response in (
        restricted_response,
        provider_response,
        model_response,
        rule_response,
        skill_response,
        definition_response,
    ):
        assert response.status_code == 409
        assert response.json()["detail"] == {
            "code": "agent_settings_locked",
            "message": "Agent 会话运行中，无法修改相关设置",
        }


@pytest.mark.asyncio
async def test_agent_settings_lock_allows_unrestricted_settings_update(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _create_agent_task(client, session, is_running=True)

    response = await client.put("/api/v1/settings", json={"theme": "dark"})

    assert response.status_code == 200
    assert response.json()["theme"] == "dark"


@pytest.mark.asyncio
async def test_cancelling_waiting_agent_session_releases_settings_lock(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    task = await _create_agent_task(client, session)
    revision = Revision(
        project_id=task.project_id,
        task_id=task.id,
        message="等待用户回答",
        agent_session_id=task.agent_session_id,
        revision_type="agent",
        status="interrupted",
        is_checkpoint=True,
        project_snapshot_title="锁定设置测试",
        project_snapshot_word_count=0,
        project_snapshot_chapter_count=0,
    )
    session.add(revision)
    await session.flush()
    task.current_revision_id = revision.id
    session.add(task)
    await session.commit()

    runner = MagicMock(project_id=task.project_id, model_config={})
    _SESSION_RUNNERS[task.agent_session_id or ""] = runner
    try:
        cancel_response = await client.post(
            f"/api/v1/agent/sessions/{task.agent_session_id}/cancel",
        )
        lock_response = await client.get("/api/v1/settings/agent-session-lock")
    finally:
        _SESSION_RUNNERS.pop(task.agent_session_id or "", None)

    assert cancel_response.status_code == 200
    runner.cancel.assert_called_once_with()
    assert lock_response.json() == {"is_locked": False}
    await session.refresh(task)
    await session.refresh(revision)
    assert task.is_running is False
    assert revision.status == "cancelled"
