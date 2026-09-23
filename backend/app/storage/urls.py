"""Shared database URL validation for deployment and migration commands."""

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def normalize_postgres_url(value: str) -> str:
    try:
        url = make_url(value)
    except ArgumentError:
        raise ValueError("Invalid PostgreSQL database URL") from None
    if url.get_backend_name() != "postgresql":
        raise ValueError("Target database URL must use PostgreSQL")
    if url.drivername not in {
        "postgresql", "postgresql+psycopg", "postgresql+psycopg_async",
    }:
        raise ValueError("PostgreSQL database URL must use the psycopg driver")
    if not url.database:
        raise ValueError("PostgreSQL database URL must include a database name")
    return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def normalize_database_url(value: str) -> str:
    try:
        url = make_url(value)
    except ArgumentError:
        raise ValueError("Invalid database URL") from None
    if url.get_backend_name() == "postgresql":
        return normalize_postgres_url(value)
    if url.drivername in {"sqlite", "sqlite+aiosqlite"} and url.database:
        return url.set(drivername="sqlite+aiosqlite").render_as_string(hide_password=False)
    raise ValueError("Database URL must use SQLite or PostgreSQL with psycopg")
