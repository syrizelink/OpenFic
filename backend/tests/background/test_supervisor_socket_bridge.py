from unittest.mock import AsyncMock, call, patch

import pytest

from app.background.runtime.supervisor import BackgroundSupervisor
from app.background.transport.messages import BackgroundEventMessage
from app.socket.handlers import agent_session_room, background_project_room


@pytest.mark.asyncio
async def test_emit_background_event_routes_to_project_room():
    supervisor = BackgroundSupervisor()
    message = BackgroundEventMessage(
        type="background_job_progress",
        job_type="summary_batch",
        job_id="job-1",
        item_id=None,
        item_type=None,
        subject_type="project",
        subject_id="proj-1",
        payload={"current": 1, "total": 2, "message": "running"},
        created_at="2026-05-23T00:00:00Z",
        project_revision=123,
    )

    with patch("app.background.runtime.supervisor.emit", AsyncMock()) as mock_emit:
        await supervisor._emit_socket_background_event(message)

    mock_emit.assert_awaited_once_with(
        "background:event",
        {
            "type": "background_job_progress",
            "job_type": "summary_batch",
            "job_id": "job-1",
            "item_id": None,
            "item_type": None,
            "subject_type": "project",
            "subject_id": "proj-1",
            "payload": {"current": 1, "total": 2, "message": "running"},
            "created_at": "2026-05-23T00:00:00Z",
            "project_revision": 123,
            "project_id": "proj-1",
        },
        room=background_project_room("proj-1"),
    )


@pytest.mark.asyncio
async def test_emit_task_title_updated_to_background_and_agent_rooms():
    supervisor = BackgroundSupervisor()
    message = BackgroundEventMessage(
        type="task_title_updated",
        job_type="session_title",
        job_id="job-2",
        item_id=None,
        item_type=None,
        subject_type="task",
        subject_id="task-1",
        payload={
            "task_id": "task-1",
            "project_id": "proj-9",
            "chapter_id": "chap-1",
            "agent_session_id": "sess-1",
            "title": "新标题",
            "updated_at": "2026-05-23T00:00:01Z",
        },
        created_at="2026-05-23T00:00:01Z",
        project_revision=456,
    )

    with patch("app.background.runtime.supervisor.emit", AsyncMock()) as mock_emit:
        await supervisor._emit_socket_background_event(message)

    assert mock_emit.await_args_list == [
        call(
            "background:event",
            {
                "type": "task_title_updated",
                "job_type": "session_title",
                "job_id": "job-2",
                "item_id": None,
                "item_type": None,
                "subject_type": "task",
                "subject_id": "task-1",
                "payload": {
                    "task_id": "task-1",
                    "project_id": "proj-9",
                    "chapter_id": "chap-1",
                    "agent_session_id": "sess-1",
                    "title": "新标题",
                    "updated_at": "2026-05-23T00:00:01Z",
                },
                "created_at": "2026-05-23T00:00:01Z",
                "project_revision": 456,
                "project_id": "proj-9",
                "task_id": "task-1",
                "chapter_id": "chap-1",
                "agent_session_id": "sess-1",
                "title": "新标题",
                "updated_at": "2026-05-23T00:00:01Z",
            },
            room=background_project_room("proj-9"),
        ),
        call(
            "agent:task_title_updated",
            {
                "session_id": "sess-1",
                "task_id": "task-1",
                "project_id": "proj-9",
                "chapter_id": "chap-1",
                "title": "新标题",
                "updated_at": "2026-05-23T00:00:01Z",
            },
            room=agent_session_room("sess-1"),
        ),
    ]
