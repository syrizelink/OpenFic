from types import SimpleNamespace

import aiosqlite

import app.storage.database as database


async def test_vacuum_database_if_needed_reclaims_large_free_space(
    monkeypatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "openfic.db"
    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(database_url=f"sqlite+aiosqlite:///{db_path}"),
    )
    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("CREATE TABLE test_data (value BLOB)")
        await conn.execute("INSERT INTO test_data(value) VALUES (zeroblob(131072))")
        await conn.execute("DELETE FROM test_data")
        await conn.commit()
    finally:
        await conn.close()

    assert await database.vacuum_database_if_needed(min_free_bytes=1) is True


async def test_vacuum_database_if_needed_skips_small_free_space(
    monkeypatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "openfic.db"
    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(database_url=f"sqlite+aiosqlite:///{db_path}"),
    )
    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("CREATE TABLE test_data (value BLOB)")
        await conn.execute("INSERT INTO test_data(value) VALUES (zeroblob(4096))")
        await conn.execute("DELETE FROM test_data")
        await conn.commit()
    finally:
        await conn.close()

    assert await database.vacuum_database_if_needed() is False
