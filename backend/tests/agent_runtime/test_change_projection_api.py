"""Agent 会话变更 API 测试。"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.agent_runtime.session_changes import (
    AgentChangeItem,
    AgentChangeSection,
    AgentChangeSummary,
    AgentSessionChanges,
    AgentTurnChanges,
)


@pytest.mark.asyncio
async def test_session_changes_api_returns_turn_and_subagent_changes(
    client: AsyncClient,
) -> None:
    summary = AgentChangeSummary(
        items=[
            AgentChangeItem(
                key="chapter:chapter-1",
                kind="chapter",
                title="章节",
                title_before="旧章节",
                title_after="章节",
                path=["第一卷"],
                operation="update",
                sections=[AgentChangeSection(type="content", lines=[])],
                source_message_id="child-tool-1",
                source="subagent",
                child_run_id="child-1",
                request_id="request-1",
                agent_key="writer",
                agent_number="#1001",
                revision_id="revision-1",
            )
        ]
    )
    changes = AgentSessionChanges(
        session_id="parent-session",
        turns=[
            AgentTurnChanges(
                revision_id="revision-1",
                user_message_id="user-1",
                user_message_seq=0,
                changes=summary,
                subagent_runs=[],
            )
        ],
        session_changes=summary,
    )

    with patch(
        "app.api.routers.agent_runtime.task_service.get_task_by_agent_session_id",
        AsyncMock(return_value=object()),
    ), patch(
        "app.api.routers.agent_runtime.load_agent_session_changes",
        AsyncMock(return_value=changes),
    ):
        response = await client.get("/api/v1/agent/sessions/parent-session/changes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "parent-session"
    assert payload["turns"][0]["revision_id"] == "revision-1"
    assert payload["turns"][0]["changes"]["items"][0]["child_run_id"] == "child-1"
    assert payload["turns"][0]["changes"]["items"][0]["path"] == ["第一卷"]
    assert payload["turns"][0]["changes"]["items"][0]["title_before"] == "旧章节"
    assert payload["session_changes"]["item_count"] == 1


@pytest.mark.asyncio
async def test_session_changes_api_skips_duplicate_explicit_response_validation(
    client: AsyncClient,
) -> None:
    changes = AgentSessionChanges(
        session_id="parent-session",
        turns=[],
        session_changes=AgentChangeSummary(items=[]),
    )

    with patch(
        "app.api.routers.agent_runtime.task_service.get_task_by_agent_session_id",
        AsyncMock(return_value=object()),
    ), patch(
        "app.api.routers.agent_runtime.load_agent_session_changes",
        AsyncMock(return_value=changes),
    ), patch(
        "app.api.routers.agent_runtime.AgentSessionChangesResponse.model_validate",
        side_effect=AssertionError("explicit response validation should be skipped"),
    ):
        response = await client.get("/api/v1/agent/sessions/parent-session/changes")

    assert response.status_code == 200
    assert response.json()["session_changes"]["item_count"] == 0
