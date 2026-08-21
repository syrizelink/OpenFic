import pytest

from app.agent_runtime.context.helpers.canonical_mentions import compile_canonical_mentions
from app.agent_runtime.context.helpers.canonical_commands import extract_referenced_skill_names


@pytest.mark.asyncio
async def test_compile_canonical_mentions_compiles_skill_command() -> None:
    compiled = await compile_canonical_mentions(
        '请使用<of-skill name="小说人物设计" />',
    )

    assert compiled == "请使用@skill:小说人物设计"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_keeps_skill_command_name_without_lookup() -> None:
    compiled = await compile_canonical_mentions(
        '<of-skill name="已禁用技能" />',
    )

    assert compiled == "@skill:已禁用技能"


def test_extract_referenced_skill_names_prefers_the_longest_matching_name() -> None:
    names = extract_referenced_skill_names(
        ["@skill:foo bar"],
        ["foo", "foo bar"],
    )

    assert names == ("foo bar",)


def test_extract_referenced_skill_names_allows_cjk_text_after_ascii_name() -> None:
    names = extract_referenced_skill_names(
        ["@skill:foo请继续"],
        ["foo"],
    )

    assert names == ("foo",)
