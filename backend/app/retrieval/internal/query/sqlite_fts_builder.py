# -*- coding: utf-8 -*-
"""Pembangun kueri untuk adapter SQLite FTS5.

Menyediakan antarmuka berantai yang sama dengan ``RetrievalQueryBuilder`` versi
LanceDB supaya pemanggil seperti ``search_chapters`` tidak perlu tahu adapter mana
yang sedang aktif. Perbedaan perilaku yang disengaja:

* Tidak ada pencarian vektor. ``hybrid()`` dan ``vector()`` diturunkan menjadi
  BM25 kata kunci, dan ``vector_top_k()`` serta ``ef()`` menjadi no-op.
* Skor dinormalisasi ke rentang 0..1 relatif terhadap kecocokan terbaik dalam
  satu hasil kueri, supaya ambang keyakinan pemanggil tetap bermakna.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.models.clients.rerank_client import RerankClient
from app.retrieval.internal.query.ranking import base_row_dict
from app.retrieval.internal.validation import validate_query_filter
from app.retrieval.types import ChunkSearchResult

if TYPE_CHECKING:
    from app.retrieval.engine_sqlite_fts import SqliteFtsRetrievalEngine


# Hanya rentang aksara yang aman untuk dijadikan token FTS5 yang dipertahankan.
# Semua tanda baca dan operator FTS5 (``"``, ``*``, ``:``, ``^``, ``(``, ``)``,
# ``-``, ``NEAR``) otomatis terbuang sehingga kueri pengguna tidak dapat
# menyuntikkan sintaksis MATCH.
_TOKEN_PATTERN = re.compile(
    r"[0-9A-Za-z"
    r"\u00c0-\u024f"  # Latin-1 dan Latin Extended (aksen)
    r"\u0400-\u04ff"  # Sirilik
    r"\u4e00-\u9fff"  # CJK terpadu
    r"\u3040-\u30ff"  # Hiragana dan Katakana
    r"]+"
)

#: Batas jumlah token yang dipakai dari satu kueri, menahan kueri sangat panjang
#: agar tidak membangun ekspresi MATCH yang mahal.
_MAX_QUERY_TOKENS = 32


def extract_match_tokens(text: str) -> list[str]:
    """Memecah kueri bebas menjadi token yang aman dipakai di ekspresi MATCH."""
    tokens = _TOKEN_PATTERN.findall(text or "")
    unique: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered not in unique:
            unique.append(lowered)
        if len(unique) >= _MAX_QUERY_TOKENS:
            break
    return unique


def build_match_expression(tokens: Sequence[str], *, operator: str) -> str | None:
    """Menyusun ekspresi MATCH FTS5 dari token yang sudah disaring.

    Setiap token dibungkus tanda kutip ganda sehingga diperlakukan sebagai frasa
    literal, bukan operator. Token dijamin bebas tanda kutip oleh
    ``_TOKEN_PATTERN``.
    """
    if not tokens:
        return None
    if operator not in ("AND", "OR"):
        raise ValueError("operator must be AND or OR")
    return f" {operator} ".join(f'"{token}"' for token in tokens)


def normalize_bm25_scores(raw_scores: Sequence[float]) -> list[float]:
    """Mengubah nilai bm25() SQLite menjadi tingkat keyakinan 0..1.

    ``bm25()`` mengembalikan bilangan negatif dengan nilai makin kecil berarti
    makin relevan. Nilai dibalik lalu dibagi kecocokan terbaik dalam kumpulan
    hasil yang sama. Karena FTS5 hanya mengembalikan baris yang benar-benar
    memuat token kueri, semua hasil sudah pasti relevan secara leksikal.
    """
    relevances = [-float(score) for score in raw_scores]
    best = max(relevances, default=0.0)
    if best <= 0:
        # Semua skor nol atau positif: kembalikan keyakinan penuh yang seragam
        # karena FTS5 sudah menjamin token kueri hadir di setiap baris.
        return [1.0 for _ in relevances]
    return [max(0.0, min(relevance / best, 1.0)) for relevance in relevances]


@dataclass(frozen=True)
class SqliteFtsQueryBuilder:
    """Pembangun kueri BM25 yang belum dieksekusi."""

    engine: SqliteFtsRetrievalEngine
    query_text: str
    bm25_top_k_count: int = 20
    limit_count: int = 10
    rerank_client: RerankClient | None = None
    rerank_top_n: int | None = None
    filters: tuple[tuple[str, Any], ...] = ()

    # -- Mode: FTS5 hanya mendukung BM25, jadi semua mode menuju jalur yang sama.

    def bm25(self) -> SqliteFtsQueryBuilder:
        return self

    def hybrid(self) -> SqliteFtsQueryBuilder:
        return self

    def vector(self) -> SqliteFtsQueryBuilder:
        raise ValueError(
            "Adapter SQLite FTS5 tidak mendukung pencarian vektor. "
            "Gunakan bm25() atau hybrid()."
        )

    # -- Parameter yang tidak berlaku pada BM25 murni: divalidasi lalu diabaikan.

    def vector_top_k(self, count: int) -> SqliteFtsQueryBuilder:
        if count <= 0:
            raise ValueError("vector_top_k must be greater than 0")
        return self

    def ef(self, ef: int) -> SqliteFtsQueryBuilder:
        if ef <= 0:
            raise ValueError("ef must be greater than 0")
        return self

    def rrf(self, *, k: int) -> SqliteFtsQueryBuilder:
        if k <= 0:
            raise ValueError("rrf k must be greater than 0")
        return self

    # -- Parameter yang benar-benar dipakai.

    def bm25_top_k(self, count: int) -> SqliteFtsQueryBuilder:
        if count <= 0:
            raise ValueError("bm25_top_k must be greater than 0")
        return replace(self, bm25_top_k_count=count)

    def limit(self, count: int) -> SqliteFtsQueryBuilder:
        if count <= 0:
            raise ValueError("limit must be greater than 0")
        return replace(self, limit_count=count)

    def rerank(
        self, rerank_client: RerankClient, *, top_n: int | None = None
    ) -> SqliteFtsQueryBuilder:
        if top_n is not None and top_n <= 0:
            raise ValueError("rerank top_n must be greater than 0")
        return replace(self, rerank_client=rerank_client, rerank_top_n=top_n)

    def filter_eq(self, field: str, value: Any) -> SqliteFtsQueryBuilder:
        validate_query_filter(self.engine.contract, field, value)
        return replace(self, filters=self.filters + ((field, value),))

    async def run(self) -> list[ChunkSearchResult]:
        tokens = extract_match_tokens(self.query_text)
        if not tokens:
            logger.info("Retrieval FTS5: kueri tidak memuat token yang dapat dicari")
            return []

        # Coba AND lebih dulu supaya kueri banyak kata mengutamakan ketepatan,
        # lalu turun ke OR bila tidak ada baris yang memuat semua token.
        rows: list[dict[str, Any]] = []
        for operator in ("AND", "OR"):
            expression = build_match_expression(tokens, operator=operator)
            if expression is None:
                continue
            rows = await self.engine.match_rows(
                expression,
                filters=self.filters,
                limit=self.bm25_top_k_count,
            )
            logger.info(
                "Retrieval FTS5: operator={} token={} baris={}",
                operator,
                len(tokens),
                len(rows),
            )
            if rows:
                break

        if not rows:
            return []

        scores = normalize_bm25_scores([row.get("_bm25_raw", 0.0) for row in rows])
        candidates: list[dict[str, Any]] = []
        for row, score in zip(rows, scores, strict=True):
            candidate = base_row_dict(row)
            candidate["score"] = score
            candidate["bm25_score"] = score
            candidate["vector_score"] = None
            candidate["rrf_score"] = None
            candidate["rerank_score"] = None
            candidate["matched_by"] = "bm25"
            candidates.append(candidate)

        if self.rerank_client is not None and candidates:
            candidates = await self._apply_rerank(candidates)

        return [
            ChunkSearchResult.model_validate(candidate)
            for candidate in candidates[: self.limit_count]
        ]

    async def _apply_rerank(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        assert self.rerank_client is not None
        top_n = min(self.rerank_top_n or len(candidates), len(candidates))
        head = candidates[:top_n]
        reranked = await self.rerank_client.rerank(
            self.query_text,
            [candidate["text"] for candidate in head],
            top_n=top_n,
        )
        ordered: list[dict[str, Any]] = []
        for item in reranked.results:
            candidate = head[item.index]
            candidate["rerank_score"] = max(0.0, min(float(item.relevance_score), 1.0))
            ordered.append(candidate)
        seen = {candidate["chunk_id"] for candidate in ordered}
        tail = [
            candidate for candidate in candidates if candidate["chunk_id"] not in seen
        ]
        return ordered + tail


__all__ = [
    "SqliteFtsQueryBuilder",
    "build_match_expression",
    "extract_match_tokens",
    "normalize_bm25_scores",
]
