# -*- coding: utf-8 -*-
"""
数据库连接与 session 管理。
"""

import os
from pathlib import Path
from collections.abc import AsyncGenerator
from time import perf_counter

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.pinyin import to_pinyin, to_pinyin_initials
from app.settings import settings

_engine = None
_async_session_factory = None
_active_main_db_transactions: dict[int, dict[str, object]] = {}
_VACUUM_MIN_FREE_BYTES = 64 * 1024 * 1024
ALEMBIC_INI_PATH = Path(
    os.getenv("OPENFIC_ALEMBIC_INI", str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)


def _main_db_wal_size() -> int | None:
    try:
        database_path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
        return Path(f"{database_path}-wal").stat().st_size
    except OSError:
        return None


def _summarize_sql(statement: str) -> str:
    summary = " ".join(statement.split())
    return summary[:160]


def _record_main_db_sql(connection, cursor, statement, parameters, context, executemany) -> None:
    connection_id = id(connection.connection)
    if connection.info.get("main_db_tx_started_at") is not None:
        summary = _summarize_sql(statement)
        connection.info["main_db_last_sql"] = summary
        transaction = _active_main_db_transactions.get(connection_id)
        if transaction is not None:
            transaction["last_sql"] = summary


def _main_db_after_begin(session, transaction, connection) -> None:
    if getattr(transaction, "parent", None) is not None:
        return
    connection_id = id(connection.connection)
    started_at = perf_counter()
    connection.info["main_db_last_sql"] = None
    connection.info["main_db_tx_started_at"] = started_at
    session.info["main_db_tx_started_at"] = started_at
    session.info["main_db_connection_id"] = connection_id
    session.info["main_db_connection"] = connection
    session.info["main_db_wal_start_bytes"] = _main_db_wal_size()
    _active_main_db_transactions[connection_id] = {
        "owner": session.info.get("main_db_owner") or "unknown",
        "started_at": started_at,
        "last_sql": None,
    }


def _active_main_db_transaction_summary(exclude_connection_id: int | None = None) -> str:
    now = perf_counter()
    active: list[str] = []
    for connection_id, transaction in _active_main_db_transactions.items():
        if connection_id == exclude_connection_id:
            continue
        started_at = transaction.get("started_at")
        age_ms = (
            int((now - started_at) * 1000) if isinstance(started_at, float) else None
        )
        active.append(
            f"{transaction.get('owner')}@{connection_id}:age_ms={age_ms}:"
            f"sql={transaction.get('last_sql')}"
        )
    return ";".join(active) or "none"


def _main_db_after_commit(session) -> None:
    started_at = session.info.pop("main_db_tx_started_at", None)
    if started_at is None:
        return
    duration_ms = int((perf_counter() - started_at) * 1000)
    owner = session.info.get("main_db_owner")
    connection = session.info.pop("main_db_connection", None)
    last_sql = connection.info.get("main_db_last_sql") if connection is not None else None
    connection_id = session.info.pop("main_db_connection_id", None)
    wal_start_bytes = session.info.pop("main_db_wal_start_bytes", None)
    if connection is not None:
        connection.info.pop("main_db_tx_started_at", None)
    transaction = _active_main_db_transactions.pop(connection_id, None)
    if transaction is not None:
        last_sql = transaction.get("last_sql") or last_sql
    if duration_ms < 500 and owner is None:
        return
    wal_end_bytes = _main_db_wal_size()
    logger.info(
        "main_db_transaction_commit owner={} connection_id={} duration_ms={} "
        "last_sql={} wal_start_bytes={} wal_end_bytes={} wal_delta_bytes={} "
        "active_transactions={}",
        owner or "unknown",
        connection_id,
        duration_ms,
        last_sql,
        wal_start_bytes,
        wal_end_bytes,
        wal_end_bytes - wal_start_bytes
        if wal_start_bytes is not None and wal_end_bytes is not None
        else None,
        _active_main_db_transaction_summary(connection_id),
    )


def _main_db_after_rollback(session) -> None:
    started_at = session.info.pop("main_db_tx_started_at", None)
    if started_at is None:
        return
    duration_ms = int((perf_counter() - started_at) * 1000)
    connection = session.info.pop("main_db_connection", None)
    last_sql = connection.info.get("main_db_last_sql") if connection is not None else None
    connection_id = session.info.pop("main_db_connection_id", None)
    session.info.pop("main_db_wal_start_bytes", None)
    if connection is not None:
        connection.info.pop("main_db_tx_started_at", None)
    transaction = _active_main_db_transactions.pop(connection_id, None)
    if transaction is not None:
        last_sql = transaction.get("last_sql") or last_sql
    if duration_ms < 500 and session.info.get("main_db_owner") is None:
        return
    logger.info(
        "main_db_transaction_rollback owner={} connection_id={} duration_ms={} last_sql={}",
        session.info.get("main_db_owner") or "unknown",
        connection_id,
        duration_ms,
        last_sql,
    )


def _main_db_after_transaction_end(session, transaction) -> None:
    if getattr(transaction, "parent", None) is not None:
        return
    connection_id = session.info.pop("main_db_connection_id", None)
    session.info.pop("main_db_tx_started_at", None)
    session.info.pop("main_db_connection", None)
    session.info.pop("main_db_wal_start_bytes", None)
    if connection_id is not None:
        _active_main_db_transactions.pop(connection_id, None)


event.listen(Engine, "before_cursor_execute", _record_main_db_sql)
event.listen(Session, "after_begin", _main_db_after_begin)
event.listen(Session, "after_commit", _main_db_after_commit)
event.listen(Session, "after_rollback", _main_db_after_rollback)
event.listen(Session, "after_transaction_end", _main_db_after_transaction_end)


def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 连接建立时设置 WAL 模式和并发优化。"""
    started_at = perf_counter()
    connection_id = id(dbapi_connection)
    logger.info(
        "sqlite_connection_start connection_id={} busy_timeout_ms=30000",
        connection_id,
    )
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
    dbapi_connection.create_function("pinyin_full", 1, to_pinyin, deterministic=True)
    dbapi_connection.create_function("pinyin_initials", 1, to_pinyin_initials, deterministic=True)
    logger.info(
        "sqlite_connection_ready connection_id={} setup_ms={}",
        connection_id,
        int((perf_counter() - started_at) * 1000),
    )


event.listen(Engine, "connect", _set_sqlite_pragma)


def _get_engine():
    """获取或创建数据库引擎。"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
            connect_args={
                "check_same_thread": False,
            },
            pool_pre_ping=True,
        )
    return _engine


def _get_session_factory():
    """获取或创建 session 工厂。"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


def _upgrade_db_to_head() -> None:
    """使用 Alembic 将数据库升级到最新版本。"""
    config = Config(str(ALEMBIC_INI_PATH))
    command.upgrade(config, "head")

async def init_db() -> None:
    """初始化数据库。"""
    logger.info("Database initialization or migration started. Please wait...")
    _upgrade_db_to_head()
    logger.info("Database initialization or migration completed.")


async def close_db() -> None:
    """
    关闭数据库连接。

    应在应用关闭时调用。
    """
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


async def vacuum_database_if_needed(
    min_free_bytes: int = _VACUUM_MIN_FREE_BYTES,
) -> bool:
    """Reclaim main database file space when deletion leaves enough free pages."""
    db_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
    if not Path(db_path).exists():
        return False

    import aiosqlite

    conn = await aiosqlite.connect(db_path)
    try:
        page_size_cursor = await conn.execute("PRAGMA page_size")
        try:
            page_size_row = await page_size_cursor.fetchone()
        finally:
            await page_size_cursor.close()
        freelist_cursor = await conn.execute("PRAGMA freelist_count")
        try:
            freelist_row = await freelist_cursor.fetchone()
        finally:
            await freelist_cursor.close()
        page_size = int(page_size_row[0]) if page_size_row else 0
        free_pages = int(freelist_row[0]) if freelist_row else 0
        if page_size * free_pages < min_free_bytes:
            return False
        await conn.execute("VACUUM")
        return True
    finally:
        await conn.close()


async def create_session() -> AsyncSession:
    """创建独立的数据库 session。"""
    session_factory = _get_session_factory()
    return session_factory()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库 session 的依赖注入函数。

    Yields:
        AsyncSession: 异步数据库 session。
    """
    session_factory = _get_session_factory()
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
