# -*- coding: utf-8 -*-
"""
Chunking helpers for retrieval indexing.

Memakai pemotongan sadar struktur: mengemas secara greedy dengan paragraf
(``\\n\\n``) sebagai unit utama; jika satu paragraf terlalu panjang, dipotong lagi
pada batas kalimat, dan bila masih terlalu panjang dipotong keras sesuai
``chunk_size``. Dibandingkan jendela geser murni per karakter, cara ini lebih baik
menjaga keutuhan unit makna dan mengurangi keterputusan makna akibat pemotongan
keras di tengah paragraf.
"""

from collections.abc import Sequence
from dataclasses import dataclass

_PARAGRAPH_SEP = "\n\n"
_SENTENCE_SEPARATORS = ("\u3002", "\uff01", "\uff1f", "!", "?", "\u2026", "\n")


@dataclass
class ChunkPiece:
    """Satu chunk: ``raw_text`` adalah isi utama (untuk dikembalikan),
    ``indexed_text`` adalah teks setelah prefiks disuntikkan yang dipakai untuk
    embedding/FTS."""

    raw_text: str
    indexed_text: str


class RecursiveCharacterChunker:
    """Pemotong sadar struktur, mempertahankan nama kontrak
    ``chunker_type="recursive_character`` tetap sama."""

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        separators: Sequence[str] | None = None,
    ) -> None:
        self.chunk_size = max(1, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size - 1))
        # separators dipertahankan sebagai parameter demi kompatibilitas tanda tangan
        # lama, tetapi logika sadar struktur tidak bergantung padanya.
        self.separators = tuple(separators or ())

    def split_text(self, text: str) -> list[str]:
        normalized = text.strip()
        if not normalized:
            return []
        if len(normalized) <= self.chunk_size:
            return [normalized]

        paragraphs = _split_paragraphs(normalized)
        chunks: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            if len(paragraph) <= self.chunk_size:
                candidate = paragraph if not buffer else f"{buffer}{_PARAGRAPH_SEP}{paragraph}"
                if len(candidate) <= self.chunk_size:
                    buffer = candidate
                    continue
                if buffer:
                    chunks.append(buffer)
                if len(paragraph) <= self.chunk_size:
                    buffer = _with_overlap(chunks, paragraph, self.chunk_overlap)
                else:
                    for piece in _split_long_paragraph(paragraph, self.chunk_size):
                        chunks.append(piece)
                    buffer = ""
                continue
            if buffer:
                chunks.append(buffer)
                buffer = ""
            for piece in _split_long_paragraph(paragraph, self.chunk_size):
                chunks.append(piece)
        if buffer:
            chunks.append(buffer)
        return [chunk for chunk in chunks if chunk]


def _split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in text.split(_PARAGRAPH_SEP) if part.strip()]


def _split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    sentences = _split_sentences(paragraph)
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(sentence) <= chunk_size:
            candidate = sentence if not buffer else f"{buffer}{sentence}"
            if len(candidate) <= chunk_size:
                buffer = candidate
                continue
            if buffer:
                pieces.append(buffer)
            buffer = sentence
            continue
        if buffer:
            pieces.append(buffer)
            buffer = ""
        pieces.extend(_hard_split(sentence, chunk_size))
    if buffer:
        pieces.append(buffer)
    return [piece for piece in pieces if piece]


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for index in range(len(text)):
        if text[index] in _SENTENCE_SEPARATORS:
            end = index + 1
            sentences.append(text[start:end])
            start = end
    if start < len(text):
        sentences.append(text[start:])
    return [s for s in sentences if s.strip()]


def _hard_split(text: str, chunk_size: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        pieces.append(text[start : start + chunk_size])
        start += chunk_size
    return pieces


def _with_overlap(
    chunks: list[str], current: str, chunk_overlap: int
) -> str:
    if chunk_overlap <= 0 or not chunks:
        return current
    tail = chunks[-1][-chunk_overlap:]
    return f"{tail}{current}"


def chunk_document(
    text: str | None,
    chunks: Sequence[str] | None,
    metadata: dict | None,
    *,
    chunk_size: int,
    chunk_overlap: int,
    skip_chunking: bool,
) -> list[ChunkPiece]:
    """Memotong satu dokumen menjadi daftar ``ChunkPiece``.

    Dipakai bersama oleh seluruh adapter retrieval supaya batas potongan dan
    penyuntikan prefiks tetap identik apa pun mesin penyimpanannya.
    """
    prefix = ""
    prefix_value = (metadata or {}).get("prefix")
    if isinstance(prefix_value, str):
        prefix = prefix_value.strip()

    def _piece(raw: str) -> ChunkPiece:
        return ChunkPiece(
            raw_text=raw,
            indexed_text=f"{prefix}\n{raw}" if prefix else raw,
        )

    if skip_chunking:
        return [_piece(chunk.strip()) for chunk in chunks or []]

    chunker = RecursiveCharacterChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return [_piece(raw) for raw in chunker.split_text(text or "")]
