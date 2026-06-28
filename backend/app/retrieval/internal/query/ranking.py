# -*- coding: utf-8 -*-
"""
Ranking and result conversion helpers for retrieval queries.
"""

from typing import Any

from app.retrieval.internal.common.codec import deserialize_metadata
from app.retrieval.types import ChunkSearchResult


def vector_score_from_distance(distance: Any) -> float | None:
    if not isinstance(distance, (int, float)):
        return None
    return 1.0 / (1.0 + float(distance))


def normalize_rrf_confidence(rrf_score: float, k: int) -> float:
    if k <= 0:
        return 0.0
    upper = 1.0 / (k + 1)
    if upper <= 0:
        return 0.0
    return max(0.0, min(rrf_score / upper, 1.0))


def _display_text(row: dict[str, Any]) -> str:
    """优先返回回传用的正文 raw_text；缺失时回退到含前缀的 text 列。"""
    raw = row.get("raw_text")
    if isinstance(raw, str) and raw:
        return raw
    return str(row.get("text", ""))


def base_row_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": str(row["document_id"]),
        "chunk_id": str(row["chunk_id"]),
        "chunk_index": int(row["chunk_index"]),
        "text": _display_text(row),
        "metadata": deserialize_metadata(row.get("metadata")),
    }


def result_from_vector_row(row: dict[str, Any]) -> ChunkSearchResult:
    vector_score = vector_score_from_distance(row.get("_distance"))
    return ChunkSearchResult(
        **base_row_dict(row),
        score=vector_score or 0.0,
        vector_score=vector_score,
        bm25_score=None,
        rrf_score=None,
        rerank_score=None,
        matched_by="vector",
    )


def result_from_bm25_row(row: dict[str, Any]) -> ChunkSearchResult:
    bm25_score = float(row.get("_score", 0.0))
    return ChunkSearchResult(
        **base_row_dict(row),
        score=bm25_score,
        vector_score=None,
        bm25_score=bm25_score,
        rrf_score=None,
        rerank_score=None,
        matched_by="bm25",
    )


def rrf_merge(
    vector_rows: list[dict[str, Any]],
    bm25_rows: list[dict[str, Any]],
    k: int,
    alpha: float = 0.7,
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rank, row in enumerate(vector_rows, start=1):
        chunk_id = str(row["chunk_id"])
        current = merged.setdefault(
            chunk_id,
            {
                **base_row_dict(row),
                "vector_score": vector_score_from_distance(row.get("_distance")),
                "bm25_score": None,
                "rrf_score": 0.0,
                "rerank_score": None,
                "matched_by": "vector",
                "score": 0.0,
            },
        )
        current["rrf_score"] += alpha / (k + rank)

    for rank, row in enumerate(bm25_rows, start=1):
        chunk_id = str(row["chunk_id"])
        current = merged.setdefault(
            chunk_id,
            {
                **base_row_dict(row),
                "vector_score": None,
                "bm25_score": float(row.get("_score", 0.0)),
                "rrf_score": 0.0,
                "rerank_score": None,
                "matched_by": "bm25",
                "score": 0.0,
            },
        )
        if current["matched_by"] == "vector":
            current["matched_by"] = "hybrid"
        current["bm25_score"] = float(row.get("_score", 0.0))
        current["rrf_score"] += (1.0 - alpha) / (k + rank)
    return merged
