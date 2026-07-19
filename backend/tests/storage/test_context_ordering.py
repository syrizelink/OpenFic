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


async def test_list_enabled_skills_by_ids_preserves_requested_order_and_filters(session):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add_all([
        Skill(
            id="skill-b",
            name="技能 B",
            summary="B",
            content="b",
            is_enabled=True,
            created_at=now,
            updated_at=now,
        ),
        Skill(
            id="skill-a",
            name="技能 A",
            summary="A",
            content="a",
            is_enabled=True,
            created_at=now,
            updated_at=now,
        ),
        Skill(
            id="skill-c",
            name="技能 C",
            summary="C",
            content="c",
            is_enabled=False,
            created_at=now,
            updated_at=now,
        ),
    ])
    await session.commit()

    result = await skill_service.list_enabled_skills_by_ids(
        session,
        ["skill-b", "skill-c", "skill-a"],
    )

    assert [item.id for item in result] == ["skill-b", "skill-a"]


async def test_list_enabled_skills_by_ids_includes_enabled_builtin_skill(session):
    result = await skill_service.list_enabled_skills_by_ids(
        session,
        ["builtin-skill--continue-chapter"],
    )

    assert [(item.id, item.name) for item in result] == [
        ("builtin-skill--continue-chapter", "章节续写")
    ]


async def test_list_skills_uses_custom_skill_offset_after_builtin_skills(session):
    builtin_skill = SimpleNamespace(
        id="builtin-skill--first",
        name="内置 Skill",
        summary="简介",
        content="内容",
        is_enabled=True,
        source="builtin",
        references=(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with patch(
        "app.storage.services.skill_service.load_builtin_skills",
        return_value=(builtin_skill,),
    ), patch(
        "app.storage.services.skill_service.skill_repo.list_by_ids",
        AsyncMock(return_value=[]),
    ), patch(
        "app.storage.services.skill_service.skill_repo.get_total",
        AsyncMock(return_value=100),
    ), patch(
        "app.storage.services.skill_service.skill_repo.list_page",
        AsyncMock(return_value=[]),
    ) as list_page:
        result = await skill_service.list_skills(session, page=10, page_size=5)

    assert result.total == 101
    list_page.assert_awaited_once_with(session, offset=44, limit=5)


async def test_list_by_version_uses_stable_tiebreakers(session):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add(
        PromptChainVersion(
            id="version-ordering",
            prompt_id="builtin-agent--writer",
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
