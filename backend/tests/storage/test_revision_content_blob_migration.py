import importlib
import zlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


migration = importlib.import_module(
    "app.storage.migrations.versions.1018_revision_content_blobs"
)


def _create_revision_blob_schema(connection: Connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE revision_content_blobs ("
            "id TEXT PRIMARY KEY, data BLOB NOT NULL, raw_size INTEGER NOT NULL)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE commits ("
            "id TEXT PRIMARY KEY, snapshot_content TEXT, "
            "snapshot_content_blob_id TEXT, new_content TEXT, "
            "new_content_blob_id TEXT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE revision_chapter_snapshots ("
            "id TEXT PRIMARY KEY, content TEXT, content_blob_id TEXT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE revision_note_snapshots ("
            "id TEXT PRIMARY KEY, content TEXT, content_blob_id TEXT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE revision_world_entry_snapshots ("
            "id TEXT PRIMARY KEY, content TEXT, content_blob_id TEXT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE revision_character_snapshots ("
            "id TEXT PRIMARY KEY, description TEXT, description_blob_id TEXT)"
        )
    )


def _insert_blob(connection: Connection, blob_id: str, content: str) -> None:
    raw = content.encode("utf-8")
    connection.execute(
        text(
            "INSERT INTO revision_content_blobs (id, data, raw_size) "
            "VALUES (:id, :data, :raw_size)"
        ),
        {"id": blob_id, "data": zlib.compress(raw), "raw_size": len(raw)},
    )


def test_restore_blob_backed_content_and_reset_marker() -> None:
    engine = create_engine("sqlite:///:memory:")
    contents = {
        "before": "提交前正文" * 200,
        "after": "提交后正文" * 200,
        "chapter": "章节快照" * 200,
        "note": "笔记快照" * 200,
        "world": "世界书快照" * 200,
        "character": "角色描述" * 200,
    }

    with engine.begin() as connection:
        _create_revision_blob_schema(connection)
        for blob_id, content in contents.items():
            _insert_blob(connection, blob_id, content)

        connection.execute(
            text(
                "INSERT INTO commits "
                "(id, snapshot_content_blob_id, new_content_blob_id) "
                "VALUES ('commit-1', 'before', 'after')"
            )
        )
        for table_name, blob_id in (
            ("revision_chapter_snapshots", "chapter"),
            ("revision_note_snapshots", "note"),
            ("revision_world_entry_snapshots", "world"),
        ):
            connection.execute(
                text(
                    f"INSERT INTO {table_name} (id, content_blob_id) "
                    "VALUES (:id, :blob_id)"
                ),
                {"id": f"{blob_id}-1", "blob_id": blob_id},
            )
        connection.execute(
            text(
                "INSERT INTO revision_character_snapshots "
                "(id, description_blob_id) VALUES ('character-1', 'character')"
            )
        )
        connection.execute(
            text("CREATE TABLE openfic_maintenance_migrations (name TEXT PRIMARY KEY)")
        )
        connection.execute(
            text(
                "INSERT INTO openfic_maintenance_migrations (name) "
                "VALUES (:backfill), ('unrelated-marker')"
            ),
            {"backfill": migration._BACKFILL_MARKER},
        )

        migration._restore_blob_backed_content(connection)
        migration._reset_backfill_marker(connection)

        commit = connection.execute(
            text(
                "SELECT snapshot_content, new_content FROM commits "
                "WHERE id = 'commit-1'"
            )
        ).mappings().one()
        assert commit["snapshot_content"] == contents["before"]
        assert commit["new_content"] == contents["after"]

        for table_name, blob_id in (
            ("revision_chapter_snapshots", "chapter"),
            ("revision_note_snapshots", "note"),
            ("revision_world_entry_snapshots", "world"),
        ):
            restored = connection.execute(
                text(f"SELECT content FROM {table_name}")
            ).scalar_one()
            assert restored == contents[blob_id]
        restored_description = connection.execute(
            text("SELECT description FROM revision_character_snapshots")
        ).scalar_one()
        assert restored_description == contents["character"]

        markers = set(
            connection.execute(
                text("SELECT name FROM openfic_maintenance_migrations")
            ).scalars()
        )
        assert markers == {"unrelated-marker"}

    engine.dispose()


def test_restore_aborts_when_referenced_blob_is_missing() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_revision_blob_schema(connection)
        connection.execute(
            text(
                "INSERT INTO revision_chapter_snapshots (id, content_blob_id) "
                "VALUES ('chapter-1', 'missing')"
            )
        )

        with pytest.raises(RuntimeError, match="references a missing"):
            migration._restore_blob_backed_content(connection)

    engine.dispose()
