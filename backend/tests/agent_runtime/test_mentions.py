import pytest

from app.agent_runtime.context.helpers import (
    CanonicalMention,
    compile_canonical_mentions,
    parse_canonical_mentions,
)
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume


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


def test_parse_canonical_mentions_keeps_text_and_tag_segments():
    parsed = parse_canonical_mentions(
        '前文<of-mention kind="chapter" chapter_id="chap_1" label="旧章节" />后文'
    )

    assert parsed[0] == "前文"
    assert isinstance(parsed[1], CanonicalMention)
    assert parsed[1].kind == "chapter"
    assert parsed[1].attrs["chapter_id"] == "chap_1"
    assert parsed[1].attrs["label"] == "旧章节"
    assert parsed[1].body == ""
    assert parsed[2] == "后文"


def test_parse_canonical_mentions_decodes_escaped_attrs_and_body():
    parsed = parse_canonical_mentions(
        '<of-mention kind="line_range" chapter_id="chap_1" label="第二章 &quot;引用&quot;">A&amp;B &lt;C&gt;</of-mention>'
    )

    assert len(parsed) == 1
    assert isinstance(parsed[0], CanonicalMention)
    assert parsed[0].attrs["label"] == '第二章 "引用"'
    assert parsed[0].body == "A&B <C>"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_renders_single_mention_as_blockquote_line(session):
    volume, _chapter = await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        '请参考<of-mention kind="volume" volume_id="vol_mentions" label="旧卷名" />后继续',
        session,
    )

    assert compiled == f"请参考\n> 引用卷：{volume.title}\n后继续"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_groups_consecutive_mentions_into_blockquotes(session):
    volume, chapter = await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        (
            '请参考<of-mention kind="volume" volume_id="vol_mentions" label="旧卷名" /> \n  '
            '<of-mention kind="chapter" chapter_id="chap_mentions" label="旧章节名" />\n'
            '<of-mention kind="line_range" chapter_id="chap_mentions" start_line="15" '
            'end_line="20" label="旧片段">快照正文</of-mention>后继续'
        ),
        session,
    )

    assert compiled == (
        "请参考\n"
        f"> 引用卷：{volume.title}\n"
        f"> 引用章节：{chapter.title}\n"
        "> 引用片段：修订后第二章 第15-20行；原文快照：快照正文\n"
        "后继续"
    )


@pytest.mark.asyncio
async def test_compile_canonical_mentions_flattens_multiline_line_range_snapshot(session):
    await _seed_story_graph(session)

    compiled = await compile_canonical_mentions(
        (
            '<of-mention kind="line_range" chapter_id="chap_mentions" start_line="15" '
            'end_line="20" label="旧片段">第一行\n第二行\n第三行</of-mention>'
        ),
        session,
    )

    assert compiled == "> 引用片段：修订后第二章 第15-20行；原文快照：第一行 第二行 第三行"


@pytest.mark.asyncio
async def test_compile_canonical_mentions_falls_back_to_stored_labels_when_missing(session):
    compiled = await compile_canonical_mentions(
        (
            '<of-mention kind="volume" volume_id="missing-volume" label="存档卷" />\n'
            '<of-mention kind="chapter" chapter_id="missing-chapter" label="存档章节" />'
            '<of-mention kind="line_range" chapter_id="missing-line" start_line="3" '
            'end_line="5" label="第二章 3-5">旧快照</of-mention>'
        ),
        session,
    )

    assert compiled == (
        "> 引用卷：存档卷\n"
        "> 引用章节：存档章节\n"
        "> 引用片段：第二章 3-5 第3-5行；原文快照：旧快照"
    )
