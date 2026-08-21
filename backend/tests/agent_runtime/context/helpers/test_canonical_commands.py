import pytest

from app.agent_runtime.context.helpers.canonical_mentions import compile_canonical_mentions
from app.agent_runtime.context.helpers.canonical_commands import (
    extract_referenced_skill_ids,
    parse_canonical_skill_commands,
)


@pytest.mark.asyncio
async def test_compile_canonical_mentions_compiles_skill_command() -> None:
    compiled = await compile_canonical_mentions(
        '请使用<of-skill id="skill-1" name="小说人物设计" />',
    )

    assert compiled == "请使用@skill:小说人物设计"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_keeps_skill_command_name_without_lookup() -> None:
    compiled = await compile_canonical_mentions(
        '<of-skill id="disabled-skill" name="已禁用技能" />',
    )

    assert compiled == "@skill:已禁用技能"


def test_canonical_skill_command_preserves_id() -> None:
    parsed = parse_canonical_skill_commands(
        '<of-skill id="skill-foo" name="foo" />',
    )

    assert parsed[0].skill_id == "skill-foo"


def test_extract_referenced_skill_ids_ignores_text_after_command() -> None:
    skill_ids = extract_referenced_skill_ids(
        ['<of-skill id="skill-foo" name="foo" /> bar'],
    )

    assert skill_ids == ("skill-foo",)


@pytest.mark.asyncio
async def test_pure_name_skill_command_is_not_compiled() -> None:
    raw = '<of-skill name="foo" />'
    compiled = await compile_canonical_mentions(raw)

    assert compiled == raw
    assert extract_referenced_skill_ids([raw]) == ()


def test_extract_referenced_skill_ids_ignores_pure_name_marker() -> None:
    skill_ids = extract_referenced_skill_ids(["@skill:foo"])

    assert skill_ids == ()
