"""PostgreSQL compatibility for published migrations."""

from __future__ import annotations

from types import ModuleType

import sqlalchemy as sa


def upgrade_dashboard_metadata_indexes(migration: ModuleType) -> None:
    """Run the published 1027 migration with PostgreSQL expressions."""
    op = migration.op
    for name, columns in migration.INDEXES:
        op.create_index(name, "agent_audit_logs", columns, unique=False)

    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.add_column(
            sa.Column("has_details", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("detail_bytes", sa.Integer(), nullable=False, server_default="0")
        )

    detail_present = " OR ".join(
        f"{column} IS NOT NULL" for column in migration.DETAIL_COLUMNS
    )
    detail_bytes = " + ".join(
        f"COALESCE(octet_length(convert_to({column}, 'UTF8')), 0)"
        for column in migration.DETAIL_COLUMNS
    )
    op.execute(
        sa.text(
            f"UPDATE agent_audit_logs SET has_details = CASE WHEN {detail_present} "
            f"THEN TRUE ELSE FALSE END, detail_bytes = {detail_bytes}"
        )
    )
    op.create_index(
        migration.DETAIL_STORAGE_INDEX,
        "agent_audit_logs",
        ["has_details", "detail_bytes"],
        unique=False,
    )
