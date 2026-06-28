# -*- coding: utf-8 -*-
"""
Chunking helpers for retrieval indexing.

采用结构感知分块：优先以段落（``\\n\\n``）为单元贪心打包，单段过长时按句子
边界二次切分，仍超长再按 ``chunk_size`` 硬切。相比纯字符滑动窗口，能更好
保留语义单元完整性，减少在段落中间硬切导致的语义断裂。
"""

from collections.abc import Sequence

_PARAGRAPH_SEP = "\n\n"
_SENTENCE_SEPARATORS = ("。", "！", "？", "!", "?", "…", "\n")


class RecursiveCharacterChunker:
    """结构感知分块器，保持 ``chunker_type="recursive_character`` 契约名不变。"""

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        separators: Sequence[str] | None = None,
    ) -> None:
        self.chunk_size = max(1, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size - 1))
        # separators 保留入参以兼容旧签名，但结构感知逻辑不依赖它。
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
