from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from app.agent_runtime.graph.state import AgentRuntimeState


@pytest.fixture
def mock_session():
    """A mocked AsyncSession that returns AsyncMock for any awaited call."""
    return AsyncMock()


@pytest.fixture
def base_state() -> AgentRuntimeState:
    return {
        "session_id": "sess_test",
        "task_id": "task_test",
        "project_id": "proj_test",
        "model_config": {
            "provider_type": "openai",
            "model_id": "gpt-test",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 100_000,
        },
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "test",
        "current_revision_id": None,
    }


@pytest.fixture
def make_state(base_state):
    def _factory(**overrides: Any) -> AgentRuntimeState:
        merged: dict[str, Any] = {**base_state, **overrides}
        return cast(AgentRuntimeState, merged)
    return _factory
