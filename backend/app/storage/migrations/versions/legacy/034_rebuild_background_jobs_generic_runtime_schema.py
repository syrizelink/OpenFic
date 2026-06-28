"""rebuild background jobs generic runtime schema

Revision ID: 034
Revises: 033
Create Date: 2026-05-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _column_or_null(table_name: str, column_name: str) -> str:
    return column_name if _has_column(table_name, column_name) else "NULL"


def _column_or_default(table_name: str, column_name: str, default_sql: str) -> str:
    return column_name if _has_column(table_name, column_name) else default_sql


def upgrade() -> None:
    queue_sql = _column_or_default("background_jobs", "queue", "'default'")
    timeout_sql = _column_or_null("background_jobs", "timeout_seconds")
    next_run_sql = _column_or_null("background_jobs", "next_run_at")
    heartbeat_sql = _column_or_null("background_jobs", "heartbeat_at")
    lease_sql = _column_or_null("background_jobs", "lease_expires_at")
    cancel_requested_sql = _column_or_null("background_jobs", "cancel_requested_at")
    cancel_reason_sql = _column_or_null("background_jobs", "cancel_reason")
    op.create_table(
        "background_jobs_new",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("queue", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("subject_type", sa.String(length=80), nullable=True),
        sa.Column("subject_id", sa.String(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("progress_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        f"""
        INSERT INTO background_jobs_new (
            id, type, status, queue, subject_type, subject_id, payload_json,
            context_json, progress_json, result_json, error_json, attempt_count,
            max_attempts, event_sequence, timeout_seconds, next_run_at, locked_by, locked_at,
            heartbeat_at, lease_expires_at, cancel_requested_at, cancel_reason,
            created_at, updated_at, started_at, finished_at
        )
        SELECT
            id,
            type,
            status,
            COALESCE({queue_sql}, 'default'),
            CASE
                WHEN task_id IS NOT NULL THEN 'task'
                WHEN chapter_id IS NOT NULL THEN 'chapter'
                WHEN project_id IS NOT NULL THEN 'project'
                ELSE NULL
            END,
            COALESCE(task_id, chapter_id, project_id),
            input_json,
            json_object(
                'project_id', project_id,
                'chapter_id', chapter_id,
                'task_id', task_id,
                'model_id', model_id,
                'model_policy', model_policy
            ),
            json_object(
                'current', progress_current,
                'total', progress_total,
                'message', progress_message
            ),
            result_json,
            CASE WHEN error_message IS NULL THEN NULL ELSE json_object('message', error_message) END,
            attempt_count,
            max_attempts,
            0,
            {timeout_sql},
            {next_run_sql},
            locked_by,
            locked_at,
            {heartbeat_sql},
            {lease_sql},
            {cancel_requested_sql},
            {cancel_reason_sql},
            created_at,
            updated_at,
            started_at,
            finished_at
        FROM background_jobs
        """
    )
    op.drop_table("background_job_events")
    op.drop_table("background_jobs")
    op.rename_table("background_jobs_new", "background_jobs")
    for column in (
        "type",
        "status",
        "queue",
        "subject_type",
        "subject_id",
        "next_run_at",
        "locked_by",
        "locked_at",
        "heartbeat_at",
        "lease_expires_at",
        "cancel_requested_at",
        "updated_at",
    ):
        op.create_index(f"ix_background_jobs_{column}", "background_jobs", [column])

    op.create_table(
        "background_job_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("item_key", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("progress_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("job_id", "item_key", "type", "status", "order_index", "updated_at"):
        op.create_index(f"ix_background_job_items_{column}", "background_job_items", [column])

    op.create_table(
        "background_job_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["background_job_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("job_id", "item_id", "sequence", "event_type", "created_at"):
        op.create_index(f"ix_background_job_events_{column}", "background_job_events", [column])


def downgrade() -> None:
    raise NotImplementedError("Downgrade from generic background job runtime schema is not supported")
