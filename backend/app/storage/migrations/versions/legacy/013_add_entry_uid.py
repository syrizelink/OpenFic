"""add entry uid for cross-version tracking

Revision ID: 013
Revises: 012
Create Date: 2025-02-09

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    添加 entry_uid 字段用于跨版本追踪条目。

    策略：
    1. 添加 uid 字段（允许 NULL）
    2. 为现有数据生成 uid（基于内容相似度匹配）
    3. 将 uid 字段设为 NOT NULL
    """
    # 1. 添加 uid 字段（允许 NULL）
    op.add_column("prompt_entries", sa.Column("uid", sa.String(), nullable=True))
    op.create_index("ix_prompt_entries_uid", "prompt_entries", ["uid"])

    # 2. 为现有数据生成 uid
    # 策略：按版本顺序处理，相同位置+相同名称的条目使用相同 uid
    conn = op.get_bind()

    # 获取所有版本（按版本号排序）
    versions_result = conn.execute(
        text("""
        SELECT id, prompt_chain_id, version_number 
        FROM prompt_chain_versions 
        ORDER BY prompt_chain_id, version_number
    """)
    )
    versions = versions_result.fetchall()

    # 按 prompt_chain 分组处理
    from collections import defaultdict

    chains_versions = defaultdict(list)
    for version in versions:
        chains_versions[version[1]].append(version)  # type: ignore[index]

    # 为每个 prompt_chain 的条目生成 uid
    for chain_id, chain_versions in chains_versions.items():
        # 存储每个版本的条目信息：{order_index: {name: uid}}
        version_entries_map: dict[str, dict[int, dict[str, str]]] = {}

        for version in chain_versions:
            version_id = version[0]

            # 获取该版本的所有条目
            entries_result = conn.execute(
                text("""
                SELECT id, name, order_index 
                FROM prompt_entries 
                WHERE version_id = :version_id 
                ORDER BY order_index
            """),
                {"version_id": version_id},
            )
            entries = entries_result.fetchall()

            current_entries: dict[int, dict[str, str]] = {}

            for entry in entries:
                entry_id, name, order_index = entry  # type: ignore[misc]

                # 检查是否有匹配的历史条目
                matched_uid = None

                # 尝试从上一个版本找到匹配的条目
                matched_uid = None

                # 策略1：相同 order_index + 相同 name
                if version_entries_map:
                    prev_version_entries = list(version_entries_map.values())[-1]
                    if (
                        order_index in prev_version_entries
                        and name in prev_version_entries[order_index]
                    ):
                        matched_uid = prev_version_entries[order_index][name]

                # 策略2：相同 name（不同位置）
                if not matched_uid and version_entries_map:
                    prev_version_entries = list(version_entries_map.values())[-1]
                    for prev_entries in prev_version_entries.values():
                        if name in prev_entries:
                            matched_uid = prev_entries[name]
                            break

                # 如果没有匹配，生成新 uid
                if not matched_uid:
                    import uuid

                    matched_uid = str(uuid.uuid4())

                # 更新数据库
                conn.execute(
                    text("""
                    UPDATE prompt_entries 
                    SET uid = :uid 
                    WHERE id = :entry_id
                """),
                    {"uid": matched_uid, "entry_id": entry_id},
                )

                # 记录当前条目
                if order_index not in current_entries:
                    current_entries[order_index] = {}
                current_entries[order_index][name] = matched_uid

            version_entries_map[version_id] = current_entries

    # 3. 将 uid 字段设为 NOT NULL
    # 注意：SQLite 不支持直接修改列约束，需要重建表
    # 但由于我们已经为所有行填充了 uid，可以在应用层强制要求
    # 如果使用 PostgreSQL/MySQL，可以执行：
    # op.alter_column('prompt_entries', 'uid', nullable=False)


def downgrade() -> None:
    """移除 uid 字段"""
    op.drop_index("ix_prompt_entries_uid", table_name="prompt_entries")
    op.drop_column("prompt_entries", "uid")
