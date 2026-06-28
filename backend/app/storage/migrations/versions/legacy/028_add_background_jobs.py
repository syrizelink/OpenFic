"""add background jobs

Revision ID: 028
Revises: 027
Create Date: 2026-05-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(length=200), nullable=True),
        sa.Column("model_policy", sa.String(length=80), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("progress_message", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "type",
        "status",
        "priority",
        "project_id",
        "chapter_id",
        "task_id",
        "locked_by",
        "locked_at",
        "updated_at",
    ):
        op.create_index(f"ix_background_jobs_{column}", "background_jobs", [column])

    op.create_table(
        "background_job_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("job_id", "project_id", "type", "created_at"):
        op.create_index(
            f"ix_background_job_events_{column}",
            "background_job_events",
            [column],
        )


def downgrade() -> None:
    for column in ("created_at", "type", "project_id", "job_id"):
        op.drop_index(f"ix_background_job_events_{column}", table_name="background_job_events")
    op.drop_table("background_job_events")

    for column in (
        "updated_at",
        "locked_at",
        "locked_by",
        "task_id",
        "chapter_id",
        "project_id",
        "priority",
        "status",
        "type",
    ):
        op.drop_index(f"ix_background_jobs_{column}", table_name="background_jobs")
    op.drop_table("background_jobs")
