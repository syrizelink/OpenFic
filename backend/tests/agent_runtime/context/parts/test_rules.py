from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from app.agent_runtime.context.parts.rules import build_rules


@pytest.mark.asyncio
async def test_rules_returns_none_when_empty(mock_session):
    with patch(
        "app.agent_runtime.context.parts.rules.agent_rule_service.list_all_rules",
        AsyncMock(return_value=[]),
    ):
        assert await build_rules(mock_session) is None


@pytest.mark.asyncio
async def test_rules_renders_pseudo_xml(mock_session):
    rules = [
        SimpleNamespace(content="不要透露身份"),
        SimpleNamespace(content="保持中文"),
    ]
    with patch(
        "app.agent_runtime.context.parts.rules.agent_rule_service.list_all_rules",
        AsyncMock(return_value=rules),
    ):
        msg = await build_rules(mock_session)
    assert msg is not None
    assert msg.role == "system"
    assert msg.metadata == {"part": "rules"}
    assert msg.content.startswith("<rules>")
    assert msg.content.endswith("</rules>")
    assert "- 不要透露身份" in msg.content
    assert "- 保持中文" in msg.content


@pytest.mark.asyncio
async def test_rules_db_error_raises_context_build_error(mock_session):
    from app.agent_runtime.context.errors import ContextBuildError
    with patch(
        "app.agent_runtime.context.parts.rules.agent_rule_service.list_all_rules",
        AsyncMock(side_effect=RuntimeError("db down")),
    ):
        with pytest.raises(ContextBuildError) as exc_info:
            await build_rules(mock_session)
    assert exc_info.value.part == "rules"
