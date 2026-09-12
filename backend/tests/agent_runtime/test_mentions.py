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
    project = Project(id="proj_mentions", title="Proyek Uji Sebutan")
    volume = Volume(
        id="vol_mentions",
        project_id=project.id,
        title="Volume 1 Revisi",
        order=1,
        chapter_count=1,
    )
    chapter = Chapter(
        id="chap_mentions",
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 2 Revisi",
        content="Baris pertama\nBaris kedua",
        word_count=2,
        order=2,
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    await session.commit()
    return volume, chapter


async def _seed_note_world_and_character(session) -> tuple[Note, WorldInfoEntry, Character]:
    project = Project(id="proj_mentions_extra", title="Proyek Sebutan Tambahan")
    note = Note(
        id="note_mentions",
        project_id=project.id,
        title="Catatan Tokoh",
        content="Baris pertama\nBaris kedua",
    )
    world_info = WorldInfo(id="wi_mentions", project_id=project.id, name="Buku Dunia Bawaan")
    world_entry = WorldInfoEntry(
        id="wie_mentions",
        world_info_id=world_info.id,
        uid=1,
        name="Setelan Kekaisaran",
        order=1,
        content="Latar satu\nLatar dua",
    )
    character = Character(
        id="char_mentions",
        project_id=project.id,
        name="Lina",
        description="Tokoh satu\nTokoh dua",
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
        'Teks awal<of-mention chapter_id="chap_1" />Teks akhir'
    )

    assert parsed[0] == "Teks awal"
    assert isinstance(parsed[1], CanonicalMention)
    assert parsed[1].kind == "chapter"
    assert parsed[1].attrs["chapter_id"] == "chap_1"
    assert parsed[1].body == ""
    assert parsed[2] == "Teks akhir"


def test_parse_canonical_mentions_decodes_escaped_attrs_and_body():
    parsed = parse_canonical_mentions(
        '<of-mention chapter_id="chap_1" line_start="15" line_end="20" label="Bab 2 &quot;kutipan&quot;">A&amp;B &lt;C&gt;</of-mention>'
    )

    assert len(parsed) == 1
    assert isinstance(parsed[0], CanonicalMention)
    assert parsed[0].kind == "chapter"
    assert parsed[0].attrs["label"] == 'Bab 2 "kutipan"'
    assert parsed[0].body == "A&B <C>"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_renders_single_mention_as_blockquote_line(session):
    volume, _chapter = await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        'Silakan lihat<of-mention volume_id="vol_mentions" />lalu lanjutkan',
        session,
    )

    assert compiled == f"Silakan lihat @volume:{volume.title} lalu lanjutkan"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_groups_consecutive_mentions_into_blockquotes(session):
    volume, chapter = await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        (
            'Silakan lihat<of-mention volume_id="vol_mentions" />\n'
            '<of-mention chapter_id="chap_mentions" />\n'
            '<of-mention chapter_id="chap_mentions" line_start="15" '
            'line_end="20">Snapshot isi utama</of-mention>lalu lanjutkan'
        ),
        session,
    )

    assert compiled == (
        f"Silakan lihat @volume:{volume.title} \n"
        f" @chapter:{volume.title}/{chapter.title} \n"
        f"@chapter:{volume.title}/{chapter.title}:15-20\n"
        "```\n"
        "Snapshot isi utama\n"
        "```\n"
        "lalu lanjutkan"
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_flattens_multiline_line_range_snapshot(session):
    await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        (
            '<of-mention chapter_id="chap_mentions" line_start="15" '
            'line_end="20">Baris pertama\nBaris kedua\nBaris ketiga</of-mention>'
        ),
        session,
    )

    assert compiled == (
        "\n"
        "@chapter:Volume 1 Revisi/Bab 2 Revisi:15-20\n"
        "```\n"
        "Baris pertama Baris kedua Baris ketiga\n"
        "```\n"
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_falls_back_to_stored_labels_when_missing(session):
    compiled = await compile_canonical_mentions(
        (
            '<of-mention volume_id="missing-volume" label="Volume Arsip" />\n'
            '<of-mention chapter_id="missing-chapter" label="Bab Arsip" />'
            '<of-mention chapter_id="missing-line" line_start="3" '
            'line_end="5" label="Bab 2 3-5">Snapshot lama</of-mention>'
        ),
        session,
    )

    assert compiled == (
        " @volume:Volume Arsip \n"
        " @chapter:Bab Arsip \n"
        "@chapter:Bab 2 3-5:3-5\n"
        "```\n"
        "Snapshot lama\n"
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
        '<of-mention note_id="note_mentions" line_start="2" line_end="3">Kutipan setelan</of-mention>',
        session,
    )

    assert compiled == (
        "\n"
        f"@note:{note.title}:2-3\n"
        "```\n"
        "Kutipan setelan\n"
        "```\n"
    )
