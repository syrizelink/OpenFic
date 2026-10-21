import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

import app.storage.database as database
from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.model import AgentRunMessage
from app.audit import repo as audit_repo
from app.settings import settings
from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.repos import (
    dashboard_repo,
    project_repo,
    revision_content_blob_repo,
    writing_activity_repo,
)


class _EmptyResult:
    def __iter__(self) -> Iterator[object]:
        return iter(())

    def scalar_one(self) -> bool:
        return False

    def one(self) -> SimpleNamespace:
        return SimpleNamespace(detail_records_count=0, detail_bytes=0)

    def all(self) -> list[object]:
        return []

    def scalars(self) -> "_EmptyResult":
        return self


class _CapturingSession:
    def __init__(self, dialect=None) -> None:
        self.statements = []
        self.dialect = dialect or sqlite.dialect()

    def get_bind(self) -> SimpleNamespace:
        return SimpleNamespace(dialect=self.dialect)

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


@pytest.mark.asyncio
@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
async def test_audit_storage_aggregates_metadata_without_reading_details(
    dialect,
) -> None:
    session = _CapturingSession(dialect)
    storage = await audit_repo.LLMAuditLogRepo(session).get_details_storage()

    assert storage == audit_repo.AuditDetailsStorage(0, 0)
    assert len(session.statements) == 1
    sql = _compiled(session.statements[0], dialect)
    assert "agent_audit_logs.has_details" in sql
    assert "sum(agent_audit_logs.detail_bytes)" in sql
    for detail in (
        "request_messages", "tool_references", "response_content",
        "response_tool_calls", "tool_call_results", "extra_data",
    ):
        assert detail not in sql
    assert "length(" not in sql


@pytest.mark.asyncio
async def test_audit_storage_persists_utf8_metadata_and_clears_details(
    session: AsyncSession,
) -> None:
    project = Project(title="audit metadata")
    session.add(project)
    await session.flush()
    values = ["\u8bf7\u6c42", "tools", "\u56de\u590d", "[]", "\u7ed3\u679c", "\u9644\u52a0"]
    detailed = LLMAuditLog(
        project_id=project.id, operation="chat", model_id="test", status="success",
        request_messages=values[0], tool_references=values[1],
        response_content=values[2], response_tool_calls=values[3],
        tool_call_results=values[4], extra_data=values[5],
    )
    empty_detail = LLMAuditLog(
        project_id=project.id, operation="chat", model_id="test", status="success",
        response_content="",
    )
    no_details = LLMAuditLog(
        project_id=project.id, operation="chat", model_id="test", status="success",
    )
    session.add_all([detailed, empty_detail, no_details])
    await session.flush()
    await session.refresh(detailed)
    await session.refresh(empty_detail)
    await session.refresh(no_details)
    expected_bytes = sum(len(value.encode("utf-8")) for value in values)
    assert expected_bytes > sum(len(value) for value in values)
    assert detailed.has_details is True
    assert detailed.detail_bytes == expected_bytes
    assert empty_detail.has_details is True
    assert empty_detail.detail_bytes == 0
    assert no_details.has_details is False
    assert no_details.detail_bytes == 0
    repo = audit_repo.LLMAuditLogRepo(session)
    assert await repo.get_details_storage() == audit_repo.AuditDetailsStorage(2, expected_bytes)
    assert await repo.clear_details() == audit_repo.ClearedAuditDetails(2, expected_bytes)
    assert await repo.get_details_storage() == audit_repo.AuditDetailsStorage(0, 0)
    await session.refresh(detailed)
    assert detailed.has_details is False
    assert detailed.detail_bytes == 0
    assert detailed.response_content is None


@pytest.mark.asyncio
@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
async def test_page_projection_context_uses_backend_json_expressions(dialect) -> None:
    session = _CapturingSession(dialect)

    assert await message_repo.load_page_projection_context(
        session, "session", ["call"], ["dispatch_subagent"],
    ) == (False, [], {})

    assert len(session.statements) == 3
    sql = "\n".join(_compiled(statement, dialect) for statement in session.statements)
    if dialect.name == "postgresql":
        assert "jsonb_array_elements(" in sql
        assert " as jsonb)" in sql
        assert "jsonb_extract_path_text(" in sql
        assert "json_each(" not in sql
        assert "json_extract(" not in sql
    else:
        assert "json_each(" in sql
        assert "json_extract(" in sql
        assert "jsonb_array_elements(" not in sql
    assert "row_number() over (partition by" in sql
    assert "agent_run_messages.seq desc" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("dispatch_source", ["caller", "tool", "other-session", "none"])
@pytest.mark.parametrize("with_call_ids", [True, False])
async def test_page_projection_context_preserves_latest_callers_and_canonical_tools(
    session: AsyncSession, dispatch_source: str, with_call_ids: bool,
) -> None:
    project = Project(title="projection context")
    session.add(project)
    await session.flush()
    task = Task(project_id=project.id, title="projection", mode="agent")
    session.add(task)
    await session.flush()
    rows = []
    for seq in range(10):
        rows.append(AgentRunMessage(
            session_id="projection", task_id=task.id, project_id=project.id,
            role="assistant", status="complete", seq=seq,
        ))
    rows[0].tool_calls = "[]"
    rows[1].tool_calls = json.dumps([
        {"id": "repeated", "name": "write_chapter", "args": {"title": "old"}},
        {"id": "second", "name": "read_chapter", "args": {}},
    ])
    rows[2].role = "tool"
    rows[2].tool_call_id = "repeated"
    rows[3].role = "tool"
    rows[3].tool_call_id = "second"
    rows[4].tool_calls = json.dumps([
        {"id": "unrequested", "name": "read_chapter", "args": {}},
        {"id": "repeated", "name": "write_chapter", "args": {"title": "latest"}},
    ])
    rows[5].role = "tool"
    rows[5].tool_call_id = "repeated"
    rows[6].role = "user"
    rows[6].tool_calls = rows[1].tool_calls
    rows[7].session_id = "other-session"
    rows[7].tool_calls = rows[1].tool_calls
    rows[8].session_id = "other-session"
    rows[8].role = "tool"
    rows[8].tool_call_id = "repeated"
    if dispatch_source == "caller":
        rows[9].tool_calls = json.dumps([
            {"id": "unrelated", "name": "read_chapter", "args": {}},
            {"id": "dispatch", "name": "dispatch_subagent", "args": {}},
        ])
    elif dispatch_source == "tool":
        rows[9].role = "tool"
        rows[9].tool_name = "dispatch_subagent"
    elif dispatch_source == "other-session":
        rows[9].session_id = "other-session"
        rows[9].tool_calls = json.dumps([{"id": "dispatch", "name": "dispatch_subagent"}])
    session.add_all(rows)
    await session.flush()
    await session.refresh(rows[2])
    await session.refresh(rows[3])

    dispatch, callers, tools = await message_repo.load_page_projection_context(
        session, "projection", ["repeated", "second", "missing"] if with_call_ids else [],
        ["dispatch_subagent"],
    )

    assert dispatch is (dispatch_source in {"caller", "tool"})
    assert [caller.id for caller in callers] == ([rows[1].id, rows[4].id] if with_call_ids else [])
    if not with_call_ids:
        assert tools == {}
        return
    assert callers[1].tool_calls[1]["args"] == {"title": "latest"}
    assert set(tools) == {"repeated", "second"}
    for call_id, first_seq, last_seq in (("repeated", 2, 5), ("second", 3, 3)):
        message_id, created_at, latest_seq = tools[call_id]
        assert message_id == rows[first_seq].id
        assert created_at == rows[first_seq].created_at
        assert latest_seq == last_seq


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


@pytest.mark.asyncio
async def test_project_search_matches_list_and_count_across_sort_orders(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "database_backend",
        session.sync_session.get_bind().dialect.name,
    )
    project = Project(title="西游记2")
    session.add(project)
    await session.flush()

    for sort_by in ("updated_at", "created_at", "title"):
        projects = await project_repo.list_all(
            session,
            search="xyj2",
            sort_by=sort_by,
            sort_order="asc",
        )

        assert [item.id for item in projects] == [project.id]
        assert await project_repo.count(session, search="xyj2") == 1


@pytest.mark.asyncio
async def test_project_search_uses_unicode_casefold_for_all_sort_fields(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "database_backend",
        session.sync_session.get_bind().dialect.name,
    )
    project = Project(title="STRASSE")
    session.add(project)
    await session.flush()

    for sort_by in ("updated_at", "created_at", "title"):
        for sort_order in ("asc", "desc"):
            projects = await project_repo.list_all(
                session,
                search="straße",
                sort_by=sort_by,
                sort_order=sort_order,
            )

            assert [item.id for item in projects] == [project.id]

    assert await project_repo.count(session, search="straße") == 1


def test_database_backend_helper_uses_configured_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(database_backend="postgresql"),
    )

    assert database.is_sqlite_backend() is False
