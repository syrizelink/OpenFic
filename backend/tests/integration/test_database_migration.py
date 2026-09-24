"""Exercise real Alembic schemas and transaction failures on disposable databases."""
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import zlib

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session

from app.agent_runtime.persistence.model import AgentAttachment
from app.storage.database import ALEMBIC_INI_PATH
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.revision_content_blob import RevisionContentBlob
from app.storage.models.task import Task
from app.storage import sqlite_to_postgres as migration


@pytest.fixture
def sqlite_source(tmp_path: Path):
    path = tmp_path / "source #1.db"
    config = Config(str(ALEMBIC_INI_PATH))
    config.attributes["database_url"] = f"sqlite:///{path}"
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "delete"
        with Session(engine) as session:
            session.add(Project(id="project", title="迁移测试", title_pinyin_full="qianyiceshi"))
            session.commit()
            task = Task(id="task", project_id="project", title="会话", mode="agent")
            session.add(task)
            session.commit()
            session.add(Revision(id="revision", project_id="project", task_id="task",
                                 message="版本", project_snapshot_title="迁移测试"))
            session.commit()
            task.current_revision_id = "revision"
            session.add(task)
            session.add(AgentAttachment(id="attachment", session_id="session", task_id="task",
                                        project_id="project", storage_name="text.txt", file_name="附件.txt",
                                        mime_type="text/plain", size_bytes=6, content="你好",
                                        content_length=2, line_count=1,
                                        created_at=datetime(2026, 9, 22, 20, tzinfo=UTC)))
            session.add(RevisionContentBlob(id="blob", data=zlib.compress(b"content"), raw_size=7,
                                           created_at=datetime(2026, 9, 22, 20, tzinfo=UTC)))
            session.commit()
        yield path
    finally:
        engine.dispose()


def test_migration_dry_run_apply_and_nonempty_rejection(sqlite_source, postgres_database_factory):
    target = postgres_database_factory()
    engine = create_engine(target, connect_args={"options": "-c timezone=UTC"})
    original = hashlib.sha256(sqlite_source.read_bytes()).hexdigest()
    try:
        preview = migration.migrate_sqlite_to_postgres(sqlite_source, target)
        assert preview.total_rows == 5
        assert inspect(engine).get_table_names() == []
        applied = migration.migrate_sqlite_to_postgres(sqlite_source, target, apply=True, batch_size=1)
        assert applied.tables == preview.tables
        assert applied.deferred_foreign_keys > 0
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT current_revision_id FROM tasks")) == "revision"
            assert conn.scalar(text("SELECT task_id FROM revisions")) == "task"
            attachment = conn.execute(text("SELECT content, width, created_at FROM agent_attachments")).one()
            assert attachment.content == "你好"
            assert attachment.width is None
            assert attachment.created_at == datetime(2026, 9, 22, 20, tzinfo=UTC)
        for apply in (False, True):
            with pytest.raises(RuntimeError, match="must be empty"):
                migration.migrate_sqlite_to_postgres(sqlite_source, target, apply=apply)
        assert hashlib.sha256(sqlite_source.read_bytes()).hexdigest() == original
        config = Config(str(ALEMBIC_INI_PATH))
        config.attributes["database_url"] = target
        command.check(config)
    finally:
        engine.dispose()


def test_migration_verification_failure_rolls_back_all_rows(sqlite_source, postgres_database_factory, monkeypatch):
    target = postgres_database_factory()
    original_verify = migration._verify_copy

    def corrupt_then_verify(source, destination, *args):
        destination.execute(text("UPDATE projects SET title = 'corrupted'"))
        original_verify(source, destination, *args)

    monkeypatch.setattr(migration, "_verify_copy", corrupt_then_verify)
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        migration.migrate_sqlite_to_postgres(sqlite_source, target, apply=True)
    engine = create_engine(target)
    try:
        with engine.connect() as conn:
            for table in migration._reflect_tables(engine).values():
                assert conn.scalar(text(f'SELECT count(*) FROM "{table.name}"')) == 0
        monkeypatch.setattr(migration, "_verify_copy", original_verify)
        assert migration.migrate_sqlite_to_postgres(sqlite_source, target, apply=True).total_rows == 5
    finally:
        engine.dispose()


def test_migration_rejects_incompatible_target_before_ddl(sqlite_source, postgres_database_factory):
    target = postgres_database_factory()
    engine = create_engine(target)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))
        for apply in (False, True):
            with pytest.raises(RuntimeError, match="current Alembic schema"):
                migration.migrate_sqlite_to_postgres(sqlite_source, target, apply=apply)
            assert inspect(engine).get_table_names() == ["unrelated"]
    finally:
        engine.dispose()


def test_postgres_upgrade_accepts_percent_encoded_password(postgres_database_factory):
    from sqlalchemy.engine import make_url

    target = make_url(postgres_database_factory()).set(password="p@ss%word").render_as_string(hide_password=False)
    migration.prepare_postgres_schema(target)
