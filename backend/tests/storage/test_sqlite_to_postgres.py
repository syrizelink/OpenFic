from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table

from app.storage.sqlite_to_postgres import (
    _copy_order,
    _rows_checksum,
    normalize_postgres_url,
)


def test_normalize_postgres_url_uses_psycopg() -> None:
    assert normalize_postgres_url("postgresql://user:pass@localhost/openfic") == (
        "postgresql+psycopg://user:pass@localhost/openfic"
    )


def test_normalize_postgres_url_rejects_non_postgres() -> None:
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        normalize_postgres_url("sqlite:///openfic.db")


def test_copy_order_defers_nullable_cycle() -> None:
    metadata = MetaData()
    projects = Table(
        "projects",
        metadata,
        Column("id", String, primary_key=True),
    )
    revisions = Table(
        "revisions",
        metadata,
        Column("id", String, primary_key=True),
        Column("task_id", String, ForeignKey("tasks.id"), nullable=True),
    )
    tasks = Table(
        "tasks",
        metadata,
        Column("id", String, primary_key=True),
        Column("project_id", String, ForeignKey(projects.c.id), nullable=False),
        Column(
            "current_revision_id",
            String,
            ForeignKey(revisions.c.id),
            nullable=True,
        ),
    )

    order = _copy_order(
        {table.name: table for table in (projects, revisions, tasks)}
    )

    assert order[0] == "projects"
    assert set(order) == {"projects", "revisions", "tasks"}


def test_copy_order_rejects_non_nullable_cycle() -> None:
    metadata = MetaData()
    left = Table(
        "left_table",
        metadata,
        Column("id", Integer, primary_key=True),
        Column(
            "right_id",
            Integer,
            ForeignKey("right_table.id"),
            nullable=False,
        ),
    )
    right = Table(
        "right_table",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("left_id", Integer, ForeignKey(left.c.id), nullable=False),
    )
    with pytest.raises(RuntimeError, match="Non-nullable foreign-key cycle"):
        _copy_order({left.name: left, right.name: right})


def test_rows_checksum_is_order_independent_and_handles_binary_and_datetime() -> None:
    now = datetime(2026, 8, 26, 10, 30, tzinfo=UTC)
    rows = [
        {"id": "b", "data": b"two", "created_at": now},
        {"id": "a", "data": b"one", "created_at": now},
    ]

    assert _rows_checksum(rows, ["id"]) == _rows_checksum(
        list(reversed(rows)), ["id"]
    )


def test_rows_checksum_treats_naive_sqlite_datetime_as_utc() -> None:
    naive = datetime(2026, 8, 26, 10, 30)
    aware = naive.replace(tzinfo=UTC)

    assert _rows_checksum([{"id": "a", "created_at": naive}], ["id"]) == (
        _rows_checksum([{"id": "a", "created_at": aware}], ["id"])
    )


def test_source_validation_rejects_old_schema(tmp_path):
    import sqlite3
    from app.storage.sqlite_to_postgres import check_sqlite_source

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
        connection.execute("INSERT INTO alembic_version VALUES ('1021')")
    with pytest.raises(RuntimeError, match="must be upgraded"):
        check_sqlite_source(path)


def test_source_validation_rejects_broken_foreign_keys(tmp_path):
    import sqlite3
    from app.storage.sqlite_to_postgres import check_sqlite_source

    path = tmp_path / "broken.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE parent (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE child (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES parent(id))")
        connection.execute("INSERT INTO child VALUES ('child', 'missing')")
    with pytest.raises(RuntimeError, match="foreign-key violations"):
        check_sqlite_source(path)
