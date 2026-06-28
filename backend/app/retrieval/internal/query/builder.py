# -*- coding: utf-8 -*-
"""
Immutable retrieval query builder.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.models.clients.rerank_client import RerankClient
from app.retrieval.internal.query.filters import build_eq_filter, render_value
from app.retrieval.internal.query.ranking import (
    normalize_rrf_confidence,
    result_from_bm25_row,
    result_from_vector_row,
    rrf_merge,
)
from app.retrieval.internal.validation import validate_query_filter
from app.retrieval.types import ChunkSearchResult

if TYPE_CHECKING:
    from app.retrieval.engine import LanceDBRetrievalEngine


@dataclass(frozen=True)
class RetrievalQueryBuilder:
    engine: LanceDBRetrievalEngine
    query_text: str
    embedding_client: Any
    mode: str = "hybrid"
    vector_top_k_count: int = 20
    bm25_top_k_count: int = 20
    limit_count: int = 10
    rrf_k: int = 60
    rerank_client: RerankClient | None = None
    rerank_top_n: int | None = None
    ef_search: int | None = None
    filters: tuple[str, ...] = ()

    def vector(self) -> "RetrievalQueryBuilder":
        return replace(self, mode="vector")

    def bm25(self) -> "RetrievalQueryBuilder":
        return replace(self, mode="bm25")

    def hybrid(self) -> "RetrievalQueryBuilder":
        return replace(self, mode="hybrid")

    def vector_top_k(self, count: int) -> "RetrievalQueryBuilder":
        if count <= 0:
            raise ValueError("vector_top_k must be greater than 0")
        return replace(self, vector_top_k_count=count)

    def bm25_top_k(self, count: int) -> "RetrievalQueryBuilder":
        if count <= 0:
            raise ValueError("bm25_top_k must be greater than 0")
        return replace(self, bm25_top_k_count=count)

    def limit(self, count: int) -> "RetrievalQueryBuilder":
        if count <= 0:
            raise ValueError("limit must be greater than 0")
        return replace(self, limit_count=count)

    def rrf(self, *, k: int) -> "RetrievalQueryBuilder":
        if k <= 0:
            raise ValueError("rrf k must be greater than 0")
        return replace(self, rrf_k=k)

    def rerank(
        self, rerank_client: RerankClient, *, top_n: int | None = None
    ) -> "RetrievalQueryBuilder":
        if top_n is not None and top_n <= 0:
            raise ValueError("rerank top_n must be greater than 0")
        return replace(self, rerank_client=rerank_client, rerank_top_n=top_n)

    def ef(self, ef: int) -> "RetrievalQueryBuilder":
        if ef <= 0:
            raise ValueError("ef must be greater than 0")
        return replace(self, ef_search=ef)

    def filter_eq(self, field: str, value: Any) -> "RetrievalQueryBuilder":
        validate_query_filter(self.engine.contract, field, value)
        return replace(self, filters=self.filters + (build_eq_filter(field, value),))

    def filter_in(self, field: str, values: Sequence[Any]) -> "RetrievalQueryBuilder":
        values = tuple(values)
        if not values:
            raise ValueError("filter_in requires at least one value")
        for value in values:
            validate_query_filter(self.engine.contract, field, value)
        escaped = ", ".join(render_value(value) for value in values)
        return replace(self, filters=self.filters + (f"{field} IN ({escaped})",))

    def filter_range(
        self, field: str, *, gte: Any | None = None, lte: Any | None = None
    ) -> "RetrievalQueryBuilder":
        if gte is None and lte is None:
            raise ValueError("filter_range requires at least one bound")
        if gte is not None:
            validate_query_filter(self.engine.contract, field, gte)
        if lte is not None:
            validate_query_filter(self.engine.contract, field, lte)
        parts: list[str] = []
        if gte is not None:
            parts.append(f"{field} >= {render_value(gte)}")
        if lte is not None:
            parts.append(f"{field} <= {render_value(lte)}")
        return replace(self, filters=self.filters + (" AND ".join(parts),))

    async def run(self) -> list[ChunkSearchResult]:
        table = await self.engine._open_table()
        where_clause = " AND ".join(self.filters) if self.filters else None

        if self.mode == "vector":
            logger.info("检索: 生成 query embedding")
            vector_query = await self.embedding_client.embed_single(self.query_text)
            logger.info("检索: 向量查询 dim={}", len(vector_query))
            query = await table.search(
                vector_query,
                query_type="vector",
                vector_column_name="vector",
            )
            query = query.distance_type(self.engine.contract.distance_metric).limit(
                self.limit_count
            )
            if where_clause:
                query = query.where(where_clause)
            rows = await query.to_list()
            return [result_from_vector_row(row) for row in rows]

        if self.mode == "bm25":
            query = await table.search(
                self.query_text,
                query_type="fts",
                fts_columns=["text"],
            )
            query = query.limit(self.limit_count)
            if where_clause:
                query = query.where(where_clause)
            rows = await query.to_list()
            return [result_from_bm25_row(row) for row in rows]

        vector_query = await self.embedding_client.embed_single(self.query_text)
        logger.info("检索: 混合查询 embedding dim={}", len(vector_query))
        vector_builder = await table.search(
            vector_query,
            query_type="vector",
            vector_column_name="vector",
        )
        vector_builder = vector_builder.distance_type(
            self.engine.contract.distance_metric
        ).limit(self.vector_top_k_count)
        if self.ef_search is not None:
            vector_builder = vector_builder.ef(self.ef_search)

        bm25_builder = await table.search(
            self.query_text,
            query_type="fts",
            fts_columns=["text"],
        )
        bm25_builder = bm25_builder.limit(self.bm25_top_k_count)

        if where_clause:
            vector_builder = vector_builder.where(where_clause)
            bm25_builder = bm25_builder.where(where_clause)

        logger.info("检索: 执行 LanceDB 查询 vector_top_k={} bm25_top_k={}", self.vector_top_k_count, self.bm25_top_k_count)
        vector_rows = await vector_builder.to_list()
        bm25_rows = await bm25_builder.to_list()
        logger.info("检索: LanceDB 查询完成 vector={} bm25={}", len(vector_rows), len(bm25_rows))

        fused = rrf_merge(vector_rows, bm25_rows, self.rrf_k)
        ordered = sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)

        # 先将所有候选的 score 统一为归一化 RRF 置信度（0~1）。
        for candidate in ordered:
            candidate["score"] = normalize_rrf_confidence(
                candidate["rrf_score"], self.rrf_k
            )

        if self.rerank_client is not None and ordered:
            top_n = min(self.rerank_top_n or len(ordered), len(ordered))
            candidates = ordered[:top_n]
            reranked = await self.rerank_client.rerank(
                self.query_text,
                [candidate["text"] for candidate in candidates],
                top_n=top_n,
            )
            reranked_order: list[dict[str, Any]] = []
            for item in reranked.results:
                candidate = candidates[item.index]
                clamped = max(0.0, min(float(item.relevance_score), 1.0))
                candidate["rerank_score"] = clamped
                reranked_order.append(candidate)
            seen = {candidate["chunk_id"] for candidate in reranked_order}
            tail = [candidate for candidate in ordered if candidate["chunk_id"] not in seen]
            ordered = reranked_order + tail

        return [
            ChunkSearchResult.model_validate(row)
            for row in ordered[: self.limit_count]
        ]
