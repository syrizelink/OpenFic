# -*- coding: utf-8 -*-
"""结构感知分块器单元测试。"""

from app.retrieval.internal.indexing.chunking import RecursiveCharacterChunker


def test_short_text_returns_single_chunk() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=10)
    assert chunker.split_text("短文本") == ["短文本"]


def test_empty_text_returns_empty() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=10)
    assert chunker.split_text("   ") == []


def test_paragraphs_packed_until_chunk_size() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=10, chunk_overlap=0)
    text = "段落一\n\n段落二\n\n段落三"
    chunks = chunker.split_text(text)
    # "段落一"(3) + sep + "段落二"(3) = 7 <= 10 -> 合并；"段落三" 超限另起。
    assert chunks == ["段落一\n\n段落二", "段落三"]


def test_long_paragraph_split_by_sentence() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=5, chunk_overlap=0)
    text = "第一句。第二句。第三句。"
    chunks = chunker.split_text(text)
    # 每句含标点 4 字符 <= 5，逐句打包：合并后超 5 则结算。
    assert all(len(c) <= 5 for c in chunks)
    assert "".join(c for c in chunks if c) == text


def test_hard_split_when_sentence_exceeds_chunk_size() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=4, chunk_overlap=0)
    text = "abcdefghij"
    chunks = chunker.split_text(text)
    assert chunks == ["abcd", "efgh", "ij"]


def test_overlap_prepends_tail_of_previous_chunk() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=6, chunk_overlap=3)
    text = "段落A内容\n\n段落B内容"
    chunks = chunker.split_text(text)
    # 第二个 chunk 应以第一个 chunk 末尾 3 字符作为重叠前缀。
    assert chunks[1].startswith(chunks[0][-3:])
