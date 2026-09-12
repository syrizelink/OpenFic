# -*- coding: utf-8 -*-
"""Tes drop_index dan pemilihan adapter pada OpenFicRetrievalService.

Berkas ini sengaja terpisah dari ``test_service.py`` karena modul itu mengimpor
``lancedb`` di tingkat modul, sehingga seluruh berkasnya tidak dapat dikumpulkan
pada CPU tanpa dukungan x86-64-v2. Skenario di sini murni keyword-only, jadi
harus tetap bisa berjalan di lingkungan tersebut.
"""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.engine_protocol import (
    KEYWORD_ONLY_DIMENSIONS,
    KEYWORD_ONLY_EMBEDDING_REF_ID,
)
from app.retrieval.engine_sqlite_fts import SqliteFtsRetrievalEngine
from app.retrieval.internal.common.naming import make_table_name
from app.retrieval.service import OpenFicRetrievalService
from app.retrieval.types import (
    FilterableField,
    FilterableFieldType,
    IndexChunk,
    RetrievalIndexContract,
)
from app.storage.repos import retrieval_index_repo


def _keyword_only_contract() -> RetrievalIndexContract:
    return RetrievalIndexContract(
        embedding_model_ref_id=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_model_id_snapshot=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_dimensions_snapshot=KEYWORD_ONLY_DIMENSIONS,
        chunk_size=400,
        chunk_overlap=40,
        filterable_fields=[
            FilterableField(name="project_id", field_type=FilterableFieldType.STRING),
            FilterableField(name="chapter_id", field_type=FilterableFieldType.STRING),
            FilterableField(name="volume_id", field_type=FilterableFieldType.STRING),
        ],
    )


def _chunk(text: str) -> IndexChunk:
    return IndexChunk(
        document_id="chapter:chapter-1",
        chunk_index=0,
        raw_text=text,
        indexed_text=text,
        attributes={
            "project_id": "project-1",
            "chapter_id": "chapter-1",
            "volume_id": "volume-1",
        },
        metadata={"source_type": "chapter"},
    )


@pytest.mark.asyncio
async def test_engine_for_selects_sqlite_fts_for_keyword_only_contract(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    """Cabang pemilihan adapter: kontrak keyword-only wajib memakai FTS5.

    Ini satu-satunya titik pemilihan adapter di seluruh sistem, jadi salah pilih
    berarti memuat pustaka native pada CPU yang tidak mendukungnya.
    """
    service = OpenFicRetrievalService(base_dir=tmp_path)
    index_key = "chapters:project-1"
    row = await service.register_index(session, index_key, _keyword_only_contract())

    engine = service._engine_for(row)

    assert isinstance(engine, SqliteFtsRetrievalEngine)


@pytest.mark.asyncio
async def test_drop_index_removes_row_and_database_file(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    service = OpenFicRetrievalService(base_dir=tmp_path)
    index_key = "chapters:project-1"
    await service.register_index(session, index_key, _keyword_only_contract())
    await service.index_chunk_batch(
        session,
        index_key,
        [_chunk("Pahlawan berjumpa naga di lembah")],
        None,
    )
    await service.finalize_chunk_index(session, index_key)

    db_path = tmp_path / f"{make_table_name(index_key)}.sqlite3"
    assert db_path.exists(), "prasyarat: berkas indeks harus ada sebelum dibuang"

    dropped = await service.drop_index(session, index_key)

    assert dropped is True
    assert not db_path.exists()
    assert await retrieval_index_repo.get_by_index_key(session, index_key) is None


@pytest.mark.asyncio
async def test_drop_index_returns_false_when_index_never_registered(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    """Aman dipanggil untuk proyek yang belum pernah diindeks."""
    service = OpenFicRetrievalService(base_dir=tmp_path)

    dropped = await service.drop_index(session, "chapters:tidak-ada")

    assert dropped is False
