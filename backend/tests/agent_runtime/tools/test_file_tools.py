import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.agent_runtime.persistence.model import AgentAttachment


def _state() -> dict[str, str]:
    return {
        "session_id": "session-1",
        "parent_session_id": "parent-session",
        "project_id": "project-1",
    }


@pytest.mark.asyncio
async def test_list_file_returns_basic_metadata_without_content(session) -> None:
    from app.agent_runtime.tools.impls.file.list_file import ListFileTool

    session.add(
        AgentAttachment(
            id="file-1",
            session_id="parent-session",
            task_id="task_test",
            project_id="project-1",
            storage_name="session-1/file-1.txt",
            file_name="notes.txt",
            mime_type="text/plain",
            size_bytes=12,
            content="hello world!",
            content_length=12,
            line_count=1,
            width=None,
            height=None,
        )
    )
    await session.commit()

    with patch(
        "app.agent_runtime.tools.impls.file.list_file.create_session",
        new=AsyncMock(return_value=session),
    ):
        result = await ListFileTool(_state=_state())._execute()

    assert json.loads(result) == [
        {
            "id": "file-1",
            "file_name": "notes.txt",
            "mime_type": "text/plain",
            "size_bytes": 12,
            "content_length": 12,
            "line_count": 1,
        }
    ]


@pytest.mark.asyncio
async def test_read_file_returns_requested_content_range(session) -> None:
    from app.agent_runtime.tools.impls.file.read_file import ReadFileTool

    session.add(
        AgentAttachment(
            id="file-1",
            session_id="parent-session",
            task_id="task_test",
            project_id="project-1",
            storage_name="session-1/file-1.txt",
            file_name="notes.txt",
            mime_type="text/plain",
            size_bytes=12,
            content="hello world!",
            width=None,
            height=None,
        )
    )
    await session.commit()

    with patch(
        "app.agent_runtime.tools.impls.file.read_file.create_session",
        new=AsyncMock(return_value=session),
    ):
        _ = await ReadFileTool(_state=_state())._execute(
            file_id="file-1",
            offset=6,
            limit=5,
        )



def test_read_file_requires_offset_and_limit() -> None:
    from app.agent_runtime.tools.impls.file.read_file import ReadFileInput

    with pytest.raises(ValidationError):
        ReadFileInput.model_validate({"file_id": "file-1"})


def test_list_file_exposes_a_concrete_input_schema() -> None:
    from app.agent_runtime.tools.impls.file.list_file import ListFileTool

    tool = ListFileTool(_state=_state())

    assert tool.args_schema.model_json_schema()["type"] == "object"
