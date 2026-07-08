import pytest

from app.agent_runtime.context.helpers import (
    CanonicalMention,
    compile_canonical_mentions,
    parse_canonical_mentions,
)
from app.storage.models.character import Character
from app.storage.models.chapter import Chapter
from app.storage.models.note import Note
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.models.world_info import WorldInfo
from app.storage.models.world_info_entry import WorldInfoEntry


async def _seed_story_graph(session) -> tuple[Volume, Chapter]:
    project = Project(id="proj_mentions", title="提及测试项目")
    volume = Volume(
        id="vol_mentions",
        project_id=project.id,
        title="修订后第一卷",
        order=1,
        chapter_count=1,
    )
    chapter = Chapter(
        id="chap_mentions",
        project_id=project.id,
        volume_id=volume.id,
        title="修订后第二章",
        content="第一行\n第二行",
        word_count=2,
        order=2,
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    await session.commit()
    return volume, chapter


async def _seed_note_world_and_character(session) -> tuple[Note, WorldInfoEntry, Character]:
    project = Project(id="proj_mentions_extra", title="提及扩展项目")
    note = Note(
        id="note_mentions",
        project_id=project.id,
        title="角色笔记",
        content="第一行\n第二行",
    )
    world_info = WorldInfo(id="wi_mentions", project_id=project.id, name="默认世界书")
    world_entry = WorldInfoEntry(
        id="wie_mentions",
        world_info_id=world_info.id,
        uid=1,
        name="帝国设定",
        order=1,
        content="背景一\n背景二",
    )
    character = Character(
        id="char_mentions",
        project_id=project.id,
        name="林夏",
        description="角色一\n角色二",
    )
    session.add(project)
    session.add(note)
    session.add(world_info)
    session.add(world_entry)
    session.add(character)
    await session.commit()
    return note, world_entry, character


def test_parse_canonical_mentions_keeps_text_and_tag_segments():
    parsed = parse_canonical_mentions(
        '前文<of-mention chapter_id="chap_1" />后文'
    )

    assert parsed[0] == "前文"
    assert isinstance(parsed[1], CanonicalMention)
    assert parsed[1].kind == "chapter"
    assert parsed[1].attrs["chapter_id"] == "chap_1"
    assert parsed[1].body == ""
    assert parsed[2] == "后文"


def test_parse_canonical_mentions_decodes_escaped_attrs_and_body():
    parsed = parse_canonical_mentions(
        '<of-mention chapter_id="chap_1" line_start="15" line_end="20" label="第二章 &quot;引用&quot;">A&amp;B &lt;C&gt;</of-mention>'
    )

    assert len(parsed) == 1
    assert isinstance(parsed[0], CanonicalMention)
    assert parsed[0].kind == "chapter"
    assert parsed[0].attrs["label"] == '第二章 "引用"'
    assert parsed[0].body == "A&B <C>"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_renders_single_mention_as_blockquote_line(session):
    volume, _chapter = await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        '请参考<of-mention volume_id="vol_mentions" />后继续',
        session,
    )

    assert compiled == f"请参考 @volume:{volume.title} 后继续"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_groups_consecutive_mentions_into_blockquotes(session):
    volume, chapter = await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        (
            '请参考<of-mention volume_id="vol_mentions" />\n'
            '<of-mention chapter_id="chap_mentions" />\n'
            '<of-mention chapter_id="chap_mentions" line_start="15" '
            'line_end="20">快照正文</of-mention>后继续'
        ),
        session,
    )

    assert compiled == (
        f"请参考 @volume:{volume.title} \n"
        f" @chapter:{volume.title}/{chapter.title} \n"
        f"@chapter:{volume.title}/{chapter.title}:15-20\n"
        "```\n"
        "快照正文\n"
        "```\n"
        "后继续"
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_flattens_multiline_line_range_snapshot(session):
    await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        (
            '<of-mention chapter_id="chap_mentions" line_start="15" '
            'line_end="20">第一行\n第二行\n第三行</of-mention>'
        ),
        session,
    )

    assert compiled == (
        "\n"
        "@chapter:修订后第一卷/修订后第二章:15-20\n"
        "```\n"
        "第一行 第二行 第三行\n"
        "```\n"
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_falls_back_to_stored_labels_when_missing(session):
    compiled = await compile_canonical_mentions(
        (
            '<of-mention volume_id="missing-volume" label="存档卷" />\n'
            '<of-mention chapter_id="missing-chapter" label="存档章节" />'
            '<of-mention chapter_id="missing-line" line_start="3" '
            'line_end="5" label="第二章 3-5">旧快照</of-mention>'
        ),
        session,
    )

    assert compiled == (
        " @volume:存档卷 \n"
        " @chapter:存档章节 \n"
        "@chapter:第二章 3-5:3-5\n"
        "```\n"
        "旧快照\n"
        "```\n"
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_supports_note_world_info_and_character(session):
    note, world_entry, character = await _seed_note_world_and_character(session)

    compiled = await compile_canonical_mentions(
        (
            '<of-mention note_id="note_mentions" />\n'
            '<of-mention world_info_entry_id="wie_mentions" />\n'
            '<of-mention character_id="char_mentions" />'
        ),
        session,
    )

    assert compiled == (
        f" @note:{note.title} \n"
        f" @world_info_entry:{world_entry.name} \n"
        f" @character:{character.name} "
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_supports_expanded_note_content(session):
    note, _world_entry, _character = await _seed_note_world_and_character(session)

    compiled = await compile_canonical_mentions(
        '<of-mention note_id="note_mentions" line_start="2" line_end="3">设定片段</of-mention>',
        session,
    )

    assert compiled == (
        "\n"
        f"@note:{note.title}:2-3\n"
        "```\n"
        "设定片段\n"
        "```\n"
    )
