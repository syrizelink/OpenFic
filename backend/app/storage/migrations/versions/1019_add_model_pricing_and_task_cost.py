"""add model pricing and task cost

Revision ID: 1019
Revises: 1018
Create Date: 2026-08-21 23:00:00.000000
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "1019"
down_revision: Union[str, Sequence[str], None] = "1018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MAX_CONTEXT_LENGTH = 2_000_000
_BUNDLED_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[3]
    / "models"
    / "catalog"
    / "assets"
    / "modelsdev-catalog.snapshot.json"
)


def _normalize_api_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().rstrip("/")


def _read_non_negative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _load_catalog_index(snapshot_path: Path) -> tuple[dict[str, str], dict[tuple[str, str, str], dict]]:
    with snapshot_path.open("r", encoding="utf-8") as file:
        snapshot = json.load(file)

    provider_urls: dict[str, str] = {}
    models: dict[tuple[str, str, str], dict] = {}
    for provider in snapshot.get("providers", []):
        if not isinstance(provider, Mapping):
            continue
        provider_type = provider.get("provider_type")
        if not isinstance(provider_type, str) or not provider_type:
            continue
        api_url = provider.get("api") or provider.get("default_url")
        if isinstance(api_url, str) and api_url.strip():
            provider_urls[provider_type] = api_url

        for model in provider.get("models", []):
            if not isinstance(model, Mapping):
                continue
            model_id = model.get("model_id")
            task_type = model.get("task_type")
            metadata = model.get("metadata")
            if (
                isinstance(model_id, str)
                and isinstance(task_type, str)
                and isinstance(metadata, dict)
            ):
                models[(provider_type, model_id, task_type)] = metadata
    return provider_urls, models


def _resolve_catalog_provider_type(
    provider_type: object,
    provider_url: object,
    provider_urls: Mapping[str, str],
) -> str | None:
    if not isinstance(provider_type, str):
        return None
    if provider_type != "openai-compatible":
        return provider_type

    normalized_url = _normalize_api_url(provider_url)
    if not normalized_url:
        return None
    return next(
        (
            catalog_provider_type
            for catalog_provider_type, catalog_url in provider_urls.items()
            if _normalize_api_url(catalog_url) == normalized_url
        ),
        None,
    )


def _backfill_model_metadata(connection, snapshot_path: Path | None = None) -> None:
    provider_urls, catalog_models = _load_catalog_index(snapshot_path or _BUNDLED_SNAPSHOT_PATH)
    rows = connection.execute(
        text(
            "SELECT models.id, models.model_id, models.task_type, "
            "model_providers.provider_type, model_providers.url "
            "FROM models JOIN model_providers "
            "ON model_providers.id = models.provider_id"
        )
    ).mappings()

    for row in rows:
        catalog_provider_type = _resolve_catalog_provider_type(
            row["provider_type"], row["url"], provider_urls
        )
        if catalog_provider_type is None:
            continue
        metadata = catalog_models.get(
            (catalog_provider_type, row["model_id"], row["task_type"])
        )
        if metadata is None:
            continue

        limit = metadata.get("limit")
        cost = metadata.get("cost")
        updates: dict[str, float | int] = {}
        if isinstance(limit, Mapping):
            context_length = _read_non_negative_number(limit.get("context"))
            if context_length is not None and context_length <= _MAX_CONTEXT_LENGTH:
                updates["context_length"] = int(context_length)
        if isinstance(cost, Mapping):
            for column, catalog_key in (
                ("input_price", "input"),
                ("output_price", "output"),
                ("cache_read_price", "cache_read"),
                ("cache_write_price", "cache_write"),
            ):
                price = _read_non_negative_number(cost.get(catalog_key))
                if price is not None:
                    updates[column] = price

        if not updates:
            continue
        assignments = ", ".join(f"{column} = :{column}" for column in updates)
        connection.execute(
            text(f"UPDATE models SET {assignments} WHERE id = :model_id"),
            {**updates, "model_id": row["id"]},
        )


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column("input_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "models",
        sa.Column("output_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "models",
        sa.Column("cache_read_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "models",
        sa.Column("cache_write_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tasks",
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
    )
    _backfill_model_metadata(op.get_bind())


def downgrade() -> None:
    op.drop_column("tasks", "cost")
    op.drop_column("models", "cache_write_price")
    op.drop_column("models", "cache_read_price")
    op.drop_column("models", "output_price")
    op.drop_column("models", "input_price")
