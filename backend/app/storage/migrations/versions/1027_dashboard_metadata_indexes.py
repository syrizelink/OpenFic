"""Keep dashboard scans on metadata indexes instead of large audit rows.

Revision ID: 1027
Revises: 1026
"""

from alembic import op
import sqlalchemy as sa

revision = "1027"
down_revision = "1026"
branch_labels = None
depends_on = None

INDEXES = (
    (
        "ix_agent_audit_logs_dashboard_metrics",
        [
            "created_at",
            "id",
            "project_id",
            "model_id",
            "model_name",
            "tokens_input",
            "tokens_output",
            "tokens_total",
            "latency_ms",
            "first_token_ms",
            "status",
            "model_provider",
            "category",
            "operation",
        ],
    ),
    ("ix_agent_audit_logs_model_id_model_name", ["model_id", "model_name"]),
)

DETAIL_STORAGE_INDEX = "ix_agent_audit_logs_detail_storage"
DETAIL_COLUMNS = (
    "request_messages",
    "tool_references",
    "response_content",
    "response_tool_calls",
    "tool_call_results",
    "extra_data",
)


def _detail_present_sql() -> str:
    return " OR ".join(f"{column} IS NOT NULL" for column in DETAIL_COLUMNS)


def _detail_bytes_sql() -> str:
    return " + ".join(
        f"COALESCE(length(CAST({column} AS BLOB)), 0)" for column in DETAIL_COLUMNS
    )


def upgrade() -> None:
    for name, columns in INDEXES:
        op.create_index(name, "agent_audit_logs", columns, unique=False)

    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.add_column(
            sa.Column("has_details", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("detail_bytes", sa.Integer(), nullable=False, server_default="0")
        )

    op.execute(
        sa.text(
            f"UPDATE agent_audit_logs SET has_details = CASE WHEN {_detail_present_sql()} "
            f"THEN 1 ELSE 0 END, detail_bytes = {_detail_bytes_sql()}"
        )
    )
    op.create_index(
        DETAIL_STORAGE_INDEX,
        "agent_audit_logs",
        ["has_details", "detail_bytes"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(DETAIL_STORAGE_INDEX, table_name="agent_audit_logs", if_exists=True)
    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.drop_column("detail_bytes")
        batch_op.drop_column("has_details")

    for name, _columns in reversed(INDEXES):
        op.drop_index(name, table_name="agent_audit_logs")
