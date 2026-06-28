from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.storage.models.prompt_chain_version import PromptChainVersion
from app.storage.models.prompt_entry import PromptEntry
from app.storage.models.skill import Skill
from app.storage.repos import prompt_entry_repo
from app.storage.services import skill_service


pytestmark = pytest.mark.asyncio


async def test_list_skills_by_skill_ids_preserves_requested_order(session):
    requested_ids = ["skill-b", "skill-a", "skill-c"]
    repo_items = [
        SimpleNamespace(skill_id="skill-a"),
        SimpleNamespace(skill_id="skill-c"),
        SimpleNamespace(skill_id="skill-b"),
    ]

    with patch(
        "app.storage.services.skill_service.skill_repo.list_by_skill_ids",
        AsyncMock(return_value=repo_items),
    ):
        result = await skill_service.list_skills_by_skill_ids(session, requested_ids)

    assert [item.skill_id for item in result] == requested_ids


async def test_list_enabled_by_skill_ids_uses_requested_order_and_filters_disabled(session):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add_all([
        Skill(
            id="skill-b",
            name="技能 B",
            summary="B",
            skill_id="skill-b",
            content="b",
            is_enabled=True,
            created_at=now,
            updated_at=now,
        ),
        Skill(
            id="skill-a",
            name="技能 A",
            summary="A",
            skill_id="skill-a",
            content="a",
            is_enabled=True,
            created_at=now,
            updated_at=now,
        ),
        Skill(
            id="skill-c",
            name="技能 C",
            summary="C",
            skill_id="skill-c",
            content="c",
            is_enabled=False,
            created_at=now,
            updated_at=now,
        ),
    ])
    await session.commit()

    result = await skill_service.list_enabled_skills_by_skill_ids(
        session,
        ["skill-b", "skill-c", "skill-a"],
    )

    assert [item.id for item in result] == ["skill-b", "skill-a"]


async def test_list_by_version_uses_stable_tiebreakers(session):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add(
        PromptChainVersion(
            id="version-ordering",
            mode_name="assistant",
            task_name="agent",
            agent_name="writer",
            version_hash="verorder",
            version_number=1,
            is_active=True,
            created_at=now,
        )
    )
    session.add_all([
        PromptEntry(
            id="entry-b",
            uid="uid-b",
            version_id="version-ordering",
            name="条目 B",
            role="system",
            content="B",
            order_index=0,
            created_at=now,
            updated_at=now,
        ),
        PromptEntry(
            id="entry-a",
            uid="uid-a",
            version_id="version-ordering",
            name="条目 A",
            role="system",
            content="A",
            order_index=0,
            created_at=now,
            updated_at=now,
        ),
    ])
    await session.commit()

    result = await prompt_entry_repo.list_by_version(session, "version-ordering")

    assert [item.id for item in result] == ["entry-a", "entry-b"]
