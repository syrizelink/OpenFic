# -*- coding: utf-8 -*-
"""Google Drive 整本 HTML 组装单元测试。"""

from app.google_drive.html_builder import (
    BookChapter,
    BookVolume,
    build_book_html,
    escape_text,
)


def _volumes() -> list[BookVolume]:
    return [
        BookVolume(id="vol-1", title="始卷", order=1),
        BookVolume(id="vol-2", title="终卷", order=2),
    ]


def _chapters() -> list[BookChapter]:
    return [
        BookChapter(id="c-1", volume_id="vol-1", title="第一章", content="第一段。\n\n第二段。"),
        BookChapter(id="c-2", volume_id="vol-1", title="第二章", content="第二章内容。"),
        BookChapter(id="c-3", volume_id="vol-2", title="最终章", content="结局。"),
    ]


def test_build_book_html_structure() -> None:
    html_doc = build_book_html("我的小说", _volumes(), _chapters())
    assert html_doc.startswith("<!DOCTYPE html>")
    assert "<title>我的小说</title>" in html_doc
    assert "<h1>我的小说</h1>" in html_doc
    assert "<h2>第一卷 始卷</h2>" in html_doc
    assert "<h2>第二卷 终卷</h2>" in html_doc
    assert "<h3>第一章</h3>" in html_doc
    assert "<h3>最终章</h3>" in html_doc
    assert html_doc.endswith("</html>")


def test_build_book_html_paragraphs_and_line_breaks() -> None:
    html_doc = build_book_html("书名", _volumes(), _chapters())
    assert "<p>第一段。</p>" in html_doc
    assert "<p>第二段。</p>" in html_doc
    assert "<p>第二章内容。</p>" in html_doc


def test_build_book_html_single_line_break() -> None:
    chapter = [BookChapter(id="c-1", volume_id="vol-1", title="标题", content="第一行\n第二行")]
    html_doc = build_book_html("书名", _volumes(), chapter)
    assert "<p>第一行<br/>第二行</p>" in html_doc


def test_build_book_html_escapes_special_characters() -> None:
    chapter = [BookChapter(id="c-1", volume_id="vol-1", title="标题", content="a < b & c")]
    html_doc = build_book_html("书名", _volumes(), chapter)
    assert "<p>a &lt; b &amp; c</p>" in html_doc
    assert "<h3>标题</h3>" in html_doc


def test_build_book_html_empty_content() -> None:
    chapter = [BookChapter(id="c-1", volume_id="vol-1", title="空章", content="")]
    html_doc = build_book_html("书名", _volumes(), chapter)
    assert "<p></p>" in html_doc


def test_build_book_html_volume_without_order() -> None:
    volumes = [BookVolume(id="vol-1", title="无编号卷", order=0)]
    chapter = [BookChapter(id="c-1", volume_id="vol-1", title="标题", content="正文")]
    html_doc = build_book_html("书名", volumes, chapter)
    assert "<h2> 无编号卷</h2>" in html_doc


def test_build_book_html_volume_dedup() -> None:
    """同一卷的连续章节只输出一次卷标题。"""
    chapters = [
        BookChapter(id="c-1", volume_id="vol-1", title="一", content="a"),
        BookChapter(id="c-2", volume_id="vol-1", title="二", content="b"),
    ]
    html_doc = build_book_html("书名", _volumes(), chapters)
    assert html_doc.count("<h2>第一卷 始卷</h2>") == 1


def test_escape_text() -> None:
    assert escape_text("<tag>") == "&lt;tag&gt;"
    assert escape_text('"quoted"') == '"quoted"'
