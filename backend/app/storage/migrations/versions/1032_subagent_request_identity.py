"""Add stable tool-call identities for replay-safe subagent notifications.

Revision ID: 1032
Revises: 1031
"""

from alembic import op
import sqlalchemy as sa

revision = "1032"
down_revision = "1031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agent_child_run_requests") as batch:
        batch.add_column(sa.Column("source_call", sa.String(200), nullable=True))
        batch.create_unique_constraint(
            "uq_child_request_source_call", ["parent_session_id", "source_call"]
        )


def downgrade():
    with op.batch_alter_table("agent_child_run_requests") as batch:
        batch.drop_constraint("uq_child_request_source_call", type_="unique")
        batch.drop_column("source_call")
