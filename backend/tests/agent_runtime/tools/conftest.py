from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_auth_hook_db():
    with patch(
        "app.agent_runtime.tools.hooks.auth._read_user_permissions",
        new=AsyncMock(return_value={}),
    ):
        yield
