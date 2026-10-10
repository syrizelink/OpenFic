"""Keep dashboard scans on metadata indexes instead of large audit rows.

Revision ID: 1027
Revises: 1026
"""

from alembic import op

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


def upgrade() -> None:
    for name, columns in INDEXES:
        op.create_index(name, "agent_audit_logs", columns, unique=False)


def downgrade() -> None:
    for name, _columns in reversed(INDEXES):
        op.drop_index(name, table_name="agent_audit_logs")
