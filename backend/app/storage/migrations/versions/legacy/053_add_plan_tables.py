"""add shared plan and plan todo tables

Revision ID: 053
Revises: 052
Create Date: 2026-06-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column_name in ["scope_id", "status", "created_at"]:
        op.create_index(f"ix_plans_{column_name}", "plans", [column_name])

    op.create_table(
        "plan_todos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "sort_index", name="uq_plan_todos_plan_id_sort_index"),
    )
    for column_name in ["plan_id", "status", "sort_index", "created_at"]:
        op.create_index(f"ix_plan_todos_{column_name}", "plan_todos", [column_name])

    with op.batch_alter_table("plans") as batch_op:
        batch_op.add_column(sa.Column("parent_dependency_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_plans_parent_dependency_id_plan_todos",
            "plan_todos",
            ["parent_dependency_id"],
            ["id"],
        )
        batch_op.create_index("ix_plans_parent_dependency_id", ["parent_dependency_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("plans") as batch_op:
        batch_op.drop_index("ix_plans_parent_dependency_id")
        batch_op.drop_constraint("fk_plans_parent_dependency_id_plan_todos", type_="foreignkey")
        batch_op.drop_column("parent_dependency_id")

    for column_name in ["created_at", "sort_index", "status", "plan_id"]:
        op.drop_index(f"ix_plan_todos_{column_name}", table_name="plan_todos")
    op.drop_table("plan_todos")

    for column_name in ["created_at", "status", "scope_id"]:
        op.drop_index(f"ix_plans_{column_name}", table_name="plans")
    op.drop_table("plans")
