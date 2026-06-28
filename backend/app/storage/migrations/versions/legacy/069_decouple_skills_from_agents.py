"""decouple skills from agents

Revision ID: 069_decouple_skills_from_agents
Revises: 068_drop_skill_order_index
Create Date: 2026-06-24 13:50:00.000000

"""

from collections import defaultdict
from datetime import UTC, datetime
import json

from alembic import op
import sqlalchemy as sa


revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


_BUILTIN_AGENT_ROWS = {
    "primary": {
        "display_name": "Orchestrator",
        "description": "负责任务拆解、调度子智能体并整合最终结果。",
        "kind": "primary",
        "prompt_agent_name": "orchestrator",
        "tool_category_keys_json": [
            "orchestration",
            "interaction",
            "plan_read",
            "plan_write",
            "chapter_read",
            "summary_read",
            "world_read",
            "note_read",
            "note_write",
        ],
        "order_index": 0,
    },
    "explorer": {
        "display_name": "Explorer",
        "description": "负责信息搜集、上下文梳理与证据查找。",
        "kind": "subagent",
        "prompt_agent_name": "explorer",
        "tool_category_keys_json": ["chapter_read", "summary_read", "world_read", "note_read"],
        "order_index": 1,
    },
    "composer": {
        "display_name": "Composer",
        "description": "负责剧情设计、结构规划与写作方案组织。",
        "kind": "subagent",
        "prompt_agent_name": "composer",
        "tool_category_keys_json": [
            "chapter_read",
            "summary_read",
            "world_read",
            "plan_read",
            "plan_write",
            "note_read",
        ],
        "order_index": 2,
    },
    "auditor": {
        "display_name": "Auditor",
        "description": "负责一致性检查、风险识别与结果审阅。",
        "kind": "subagent",
        "prompt_agent_name": "auditor",
        "tool_category_keys_json": ["chapter_read", "summary_read", "world_read", "plan_read", "note_read"],
        "order_index": 3,
    },
    "writer": {
        "display_name": "Writer",
        "description": "负责章节内容撰写、补写与正文修改。",
        "kind": "subagent",
        "prompt_agent_name": "writer",
        "tool_category_keys_json": [
            "chapter_read",
            "summary_read",
            "world_read",
            "plan_read",
            "chapter_write",
            "note_read",
            "note_write",
        ],
        "order_index": 4,
    },
    "actor": {
        "display_name": "Actor",
        "description": "负责按既定目标执行修改并推进具体动作。",
        "kind": "subagent",
        "prompt_agent_name": "actor",
        "tool_category_keys_json": [
            "chapter_read",
            "summary_read",
            "world_read",
            "plan_read",
            "chapter_write",
            "note_read",
            "note_write",
        ],
        "order_index": 5,
    },
    "reviewer": {
        "display_name": "Reviewer",
        "description": "负责产出评审意见、指出问题并提出修正建议。",
        "kind": "subagent",
        "prompt_agent_name": "reviewer",
        "tool_category_keys_json": ["chapter_read", "summary_read", "world_read", "plan_read"],
        "order_index": 6,
    },
}


def upgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_agent_definitions")
    connection.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_skills")

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "enabled_skill_ids_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    skills_rows = connection.execute(
        sa.text(
            """
            SELECT skill_id, agent_name
            FROM skills
            WHERE is_enabled = 1 AND skill_id != ''
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()

    enabled_by_agent: dict[str, list[str]] = defaultdict(list)
    for row in skills_rows:
        agent_name = row["agent_name"]
        skill_id = row["skill_id"]
        if not agent_name or not skill_id:
            continue
        if skill_id not in enabled_by_agent[agent_name]:
            enabled_by_agent[agent_name].append(skill_id)

    now = datetime.now(UTC)
    for agent_key, skill_ids in enabled_by_agent.items():
        existing = connection.execute(
            sa.text("SELECT id FROM agent_definitions WHERE key = :key"),
            {"key": agent_key},
        ).mappings().first()

        if existing is not None:
            connection.execute(
                sa.text(
                    "UPDATE agent_definitions SET enabled_skill_ids_json = :enabled_skill_ids_json WHERE key = :key"
                ),
                {
                    "key": agent_key,
                    "enabled_skill_ids_json": json.dumps(skill_ids, ensure_ascii=True),
                },
            )
            continue

        defaults = _BUILTIN_AGENT_ROWS.get(agent_key)
        if defaults is None:
            continue

        connection.execute(
            sa.text(
                """
                INSERT INTO agent_definitions (
                    id,
                    key,
                    display_name,
                    description,
                    kind,
                    prompt_agent_name,
                    model_id,
                    tool_category_keys_json,
                    skill_policy,
                    enabled_skill_ids_json,
                    metadata_json,
                    enabled,
                    order_index,
                    source,
                    delegatable_agents,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :key,
                    :display_name,
                    :description,
                    :kind,
                    :prompt_agent_name,
                    :model_id,
                    :tool_category_keys_json,
                    :skill_policy,
                    :enabled_skill_ids_json,
                    :metadata_json,
                    :enabled,
                    :order_index,
                    :source,
                    :delegatable_agents,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": f"mig-{agent_key}-skills",
                "key": agent_key,
                "display_name": defaults["display_name"],
                "description": defaults["description"],
                "kind": defaults["kind"],
                "prompt_agent_name": defaults["prompt_agent_name"],
                "model_id": None,
                "tool_category_keys_json": json.dumps(defaults["tool_category_keys_json"], ensure_ascii=True),
                "skill_policy": "disabled" if agent_key == "primary" else "enabled_by_agent",
                "enabled_skill_ids_json": json.dumps(skill_ids, ensure_ascii=True),
                "metadata_json": "{}",
                "enabled": True,
                "order_index": defaults["order_index"],
                "source": "builtin",
                "delegatable_agents": "[]",
                "created_at": now,
                "updated_at": now,
            },
        )

    connection.exec_driver_sql("DROP INDEX IF EXISTS ix_skills_agent_name")

    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_column("agent_name")

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("skill_policy")


def downgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_agent_definitions")
    connection.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_skills")

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "skill_policy",
                sa.String(length=50),
                nullable=False,
                server_default="disabled",
            )
        )

    with op.batch_alter_table("skills") as batch_op:
        batch_op.add_column(
            sa.Column(
                "agent_name",
                sa.String(length=50),
                nullable=False,
                server_default="writer",
            )
        )

    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_skills_agent_name ON skills (agent_name)"
    )

    definition_rows = connection.execute(
        sa.text(
            "SELECT key, enabled_skill_ids_json FROM agent_definitions ORDER BY order_index ASC, key ASC"
        )
    ).mappings()

    first_agent_by_skill_id: dict[str, str] = {}
    for row in definition_rows:
        raw_value = row["enabled_skill_ids_json"]
        if raw_value in (None, ""):
            continue
        skill_ids = raw_value if isinstance(raw_value, list) else json.loads(raw_value)
        for skill_id in skill_ids:
            if skill_id and skill_id not in first_agent_by_skill_id:
                first_agent_by_skill_id[skill_id] = row["key"]

    for skill_id, agent_key in first_agent_by_skill_id.items():
        connection.execute(
            sa.text("UPDATE skills SET agent_name = :agent_name WHERE skill_id = :skill_id"),
            {"agent_name": agent_key, "skill_id": skill_id},
        )

    connection.execute(
        sa.text("UPDATE agent_definitions SET skill_policy = 'disabled'")
    )

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("enabled_skill_ids_json")
