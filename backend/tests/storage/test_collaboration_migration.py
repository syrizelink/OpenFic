"""Rebase migration compatibility with main and earlier experimental databases."""

from alembic import command
import pytest
from sqlalchemy import create_engine, inspect, text

from app.storage.database_migration import _create_alembic_config
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume


@pytest.mark.parametrize("experimental_revision", [False, True])
def test_collaboration_upgrade_keeps_main_and_experimental_data(
    tmp_path, experimental_revision
):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            config = _create_alembic_config(database_url, connection)
            command.upgrade(config, "1029")
            connection.execute(
                Project.__table__.insert(), {"id": "project", "title": "keep project"}
            )
            connection.execute(
                Volume.__table__.insert(),
                {
                    "id": "volume",
                    "project_id": "project",
                    "title": "volume",
                    "order": 1,
                },
            )
            connection.execute(
                Chapter.__table__.insert(),
                {
                    "id": "chapter",
                    "project_id": "project",
                    "volume_id": "volume",
                    "title": "chapter",
                    "content": "保留章节正文🙂",
                    "word_count": 6,
                    "order": 1,
                },
            )
            if experimental_revision:
                # This is the schema produced by the previous feature branch's 1030,
                # before main assigned 1030 to quick prompts.
                connection.execute(
                    text(
                        "CREATE TABLE chapter_collaboration (chapter_id VARCHAR PRIMARY KEY REFERENCES chapters(id) ON DELETE CASCADE, epoch VARCHAR NOT NULL, state BLOB, version INTEGER NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO chapter_collaboration VALUES (:chapter_id, :epoch, :state, :version)"
                    ),
                    {
                        "chapter_id": "chapter",
                        "epoch": "keep-epoch",
                        "state": b"keep-crdt-history",
                        "version": 7,
                    },
                )
                command.stamp(config, "1030")
            else:
                command.upgrade(config, "1030")
                connection.execute(
                    text(
                        "INSERT INTO quick_prompts (id, command, content, scope, project_id) VALUES ('prompt', 'keep', 'keep prompt', 'global', NULL)"
                    )
                )
            command.upgrade(config, "head")
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "1031"
            )
            assert (
                connection.execute(
                    text("SELECT content FROM chapters WHERE id='chapter'")
                ).scalar_one()
                == "保留章节正文🙂"
            )
            assert {"quick_prompts", "chapter_collaboration"} <= set(
                inspect(connection).get_table_names()
            )
            assert "ix_quick_prompts_project_id" in {
                index["name"]
                for index in inspect(connection).get_indexes("quick_prompts")
            }
            if experimental_revision:
                assert connection.execute(
                    text(
                        "SELECT epoch, state, version FROM chapter_collaboration WHERE chapter_id='chapter'"
                    )
                ).one() == ("keep-epoch", b"keep-crdt-history", 7)
            else:
                assert (
                    connection.execute(
                        text("SELECT content FROM quick_prompts WHERE id='prompt'")
                    ).scalar_one()
                    == "keep prompt"
                )
    finally:
        engine.dispose()


def test_collaboration_migration_can_generate_offline_sql(tmp_path):
    from io import StringIO

    output = StringIO()
    config = _create_alembic_config(f"sqlite:///{tmp_path / 'unused.db'}")
    config.output_buffer = output
    command.upgrade(config, "1030:head", sql=True)
    assert "CREATE TABLE chapter_collaboration" in output.getvalue()
    assert "1031" in output.getvalue()
