# -*- coding: utf-8 -*-
"""Uji unit pemecah chunk yang sadar struktur."""

from app.retrieval.internal.indexing.chunking import RecursiveCharacterChunker


def test_short_text_returns_single_chunk() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=10)
    assert chunker.split_text("Teks pendek") == ["Teks pendek"]


def test_empty_text_returns_empty() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=10)
    assert chunker.split_text("   ") == []


def test_paragraphs_packed_until_chunk_size() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=10, chunk_overlap=0)
    text = "段落一\n\n段落二\n\n段落三"
    chunks = chunker.split_text(text)
    # Paragraf 1 (3 karakter) + separator + paragraf 2 (3 karakter) = 7 <= 10 -> digabung;
    # paragraf 3 melebihi batas sehingga memulai chunk baru.
    # Fixture CJK dipertahankan: assertion bergantung pada jumlah karakter.
    assert chunks == ["段落一\n\n段落二", "段落三"]


def test_long_paragraph_split_by_sentence() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=5, chunk_overlap=0)
    text = "第一句。第二句。第三句。"
    chunks = chunker.split_text(text)
    # Setiap kalimat termasuk tanda baca = 4 karakter <= 5, dikemas per kalimat:
    # bila gabungannya melebihi 5 maka chunk ditutup.
    # Fixture CJK dipertahankan: assertion bergantung pada jumlah karakter.
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
    # chunk kedua harus memakai 3 karakter terakhir chunk pertama sebagai prefiks tumpang tindih.
    # Fixture CJK dipertahankan: assertion bergantung pada jumlah karakter.
    assert chunks[1].startswith(chunks[0][-3:])
