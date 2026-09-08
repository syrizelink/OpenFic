from __future__ import annotations

from app.core.document_import import ImportDocument, normalize_document_import


def test_normalize_ordered_text_documents() -> None:
    result = normalize_document_import(
        [
            ImportDocument("first.txt", "第一章 开始\n\n正文".encode()),
            ImportDocument("second.md", "第二章 继续\n\n内容".encode()),
        ],
        structure_mode="separate_volumes",
    )

    assert [volume.title for volume in result.volumes] == ["first", "second"]
    assert [volume.chapters[0].title for volume in result.volumes] == [
        "第一章 开始",
        "第二章 继续",
    ]


def test_normalize_merged_documents_uses_continuous_chapter_numbering() -> None:
    result = normalize_document_import(
        [
            ImportDocument("rain.txt", "第十章 雨夜".encode()),
            ImportDocument("return.md", "归途".encode()),
        ],
        structure_mode="merge_volume",
        merged_volume_title="合集",
        chapter_title_mode="continuous_numbering",
    )

    assert [volume.title for volume in result.volumes] == ["合集"]
    assert [chapter.title for chapter in result.volumes[0].chapters] == [
        "第 1 章 雨夜",
        "第 2 章 归途",
    ]
