from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.storage.services.skill_service import search_enabled_skills


@pytest.mark.asyncio
async def test_empty_skill_command_query_returns_ten_most_recent_skills() -> None:
    now = datetime(2026, 8, 21, tzinfo=UTC)
    skills = [
        SimpleNamespace(
            id=f"skill-{index}",
            name=f"技能 {index}",
            updated_at=now - timedelta(minutes=index),
        )
        for index in range(12)
    ]
    skills[0].updated_at = now.replace(tzinfo=None)

    with patch(
        "app.storage.services.skill_service.list_enabled_skills",
        AsyncMock(return_value=skills),
    ):
        result = await search_enabled_skills(AsyncMock(), "", limit=20)

    assert [skill.id for skill in result] == [f"skill-{index}" for index in range(10)]
