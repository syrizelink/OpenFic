from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite

import app.storage.database as database
from app.audit import repo as audit_repo
from app.settings import settings
from app.storage.models.project import Project
from app.storage.repos import (
    dashboard_repo,
    project_repo,
    revision_content_blob_repo,
    writing_activity_repo,
)


class _EmptyResult:
    def all(self) -> list[object]:
        return []

    def scalars(self) -> "_EmptyResult":
        return self


class _CapturingSession:
    def __init__(self) -> None:
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _EmptyResult()


def _compiled(statement, dialect) -> str:
    return str(statement.compile(dialect=dialect)).lower()


@pytest.mark.asyncio
async def test_dashboard_stats_uses_a_portable_utc_date_expression() -> None:
    session = _CapturingSession()

    await dashboard_repo.get_stats(session, dashboard_repo.DashboardFilters())

    assert len(session.statements) == 1
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        sql = _compiled(session.statements[0], dialect)
        assert "strftime" not in sql
        assert "materialized" not in sql
        assert "substr(" in sql


@pytest.mark.asyncio
async def test_writing_activity_aggregates_uses_a_portable_utc_date_expression() -> None:
    session = _CapturingSession()

    await writing_activity_repo.get_aggregates(
        session,
        writing_activity_repo.WritingActivityFilters(),
    )

    assert len(session.statements) == 1
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        sql = _compiled(session.statements[0], dialect)
        assert "strftime" not in sql
        assert "materialized" not in sql
        assert "substr(" in sql


@pytest.mark.asyncio
async def test_blob_put_uses_postgresql_upsert_and_keeps_return_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_backend", "postgresql")
    session = _CapturingSession()
    text = "长正文" * 200

    blob_id = await revision_content_blob_repo.put(session, text)

    assert blob_id == revision_content_blob_repo.blob_id_for_text(text)
    sql = _compiled(session.statements[0], postgresql.dialect())
    assert "on conflict (id) do nothing" in sql


def test_audit_detail_bytes_use_utf8_length_on_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_backend", "postgresql")

    expression = audit_repo.LLMAuditLogRepo._detail_bytes_expression()
    sql = _compiled(expression, postgresql.dialect())

    assert "octet_length(" in sql
    assert "cast(" not in sql


def test_audit_detail_bytes_keep_sqlite_blob_length_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_backend", "sqlite")

    expression = audit_repo.LLMAuditLogRepo._detail_bytes_expression()
    sql = _compiled(expression, sqlite.dialect())

    assert "length(cast(" in sql
    assert " as blob)" in sql


def test_project_postgresql_search_does_not_call_sqlite_pinyin_udfs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_backend", "postgresql")

    statement = project_repo._apply_search(select(Project), "hxxm")
    sql = _compiled(statement, postgresql.dialect())

    assert "pinyin_full" not in sql
    assert "pinyin_initials" not in sql
    assert "projects.title" in sql
    assert "projects.description" in sql


@pytest.mark.asyncio
async def test_project_postgresql_title_sort_is_applied_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_backend", "postgresql")
    session = _CapturingSession()

    await project_repo.list_all(session, sort_by="title", sort_order="asc")

    sql = _compiled(session.statements[0], postgresql.dialect())
    assert "pinyin_full" not in sql
    assert "order by" not in sql


def test_database_backend_helper_uses_configured_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(database_backend="postgresql"),
    )

    assert database.is_sqlite_backend() is False
