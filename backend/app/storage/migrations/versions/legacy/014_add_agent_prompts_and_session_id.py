"""add agent prompts and session id to tasks

Revision ID: 014
Revises: 013
Create Date: 2026-02-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agent prompts and agent_session_id to tasks table."""
    from datetime import UTC, datetime
    from app.core.ids import generate_id

    conn = op.get_bind()
    now = datetime.now(UTC)

    # 1. 添加 agent_session_id 字段到 tasks 表
    op.add_column(
        "tasks",
        sa.Column("agent_session_id", sa.String(), nullable=True),
    )
    op.create_index("ix_tasks_agent_session_id", "tasks", ["agent_session_id"])

    # 2. 创建 assistant > agent > clarifier 提示词链
    clarifier_chain_id = generate_id()
    clarifier_version_id = generate_id()
    clarifier_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": clarifier_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "clarifier",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": clarifier_version_id,
            "prompt_chain_id": clarifier_chain_id,
            "version_hash": clarifier_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "初始版本",
            "created_at": now,
        },
    )

    # Clarifier 提示词条目
    clarifier_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": clarifier_version_id,
            "name": "系统角色",
            "role": "system",
            "content": """你是一位专业的需求分析师，擅长分析用户的创作请求。

你的任务是：
1. 仔细分析用户的请求
2. 判断请求是否清晰、完整
3. 如果请求模糊或缺少关键信息，生成澄清问题

判断标准：
- 如果用户请求非常具体明确，不需要澄清
- 如果用户请求过于笼统、模糊，需要澄清
- 如果缺少关键的情节、角色、场景信息，需要澄清""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": clarifier_version_id,
            "name": "输出格式",
            "role": "user",
            "content": """输出格式（严格的JSON）：
{
    "needs_clarification": true/false,
    "questions": ["问题1", "问题2", ...]
}

注意：
- 如果不需要澄清，questions 应该是空数组
- 问题应该简洁明了，一次最多3个问题
- 只在真正需要时才提问，不要过度提问""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 100,
        },
    ]

    for entry in clarifier_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )

    # 3. 创建 assistant > agent > designer 提示词链
    designer_chain_id = generate_id()
    designer_version_id = generate_id()
    designer_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": designer_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "designer",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": designer_version_id,
            "prompt_chain_id": designer_chain_id,
            "version_hash": designer_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "初始版本",
            "created_at": now,
        },
    )

    # Designer 提示词条目
    designer_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": designer_version_id,
            "name": "系统角色",
            "role": "system",
            "content": """你是一位资深的故事架构师，擅长设计引人入胜的故事情节。

你的任务是：
根据用户的需求，设计一个详细的章节大纲。

大纲应该包括：
1. 场景设定（时间、地点、氛围）
2. 主要情节点（开端、发展、高潮、结尾）
3. 角色动作和对话要点
4. 情感基调和节奏控制
5. 与前文的衔接点""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": designer_version_id,
            "name": "输出格式",
            "role": "user",
            "content": """输出格式：
使用清晰的结构化文本，分段描述各个部分。
不要使用 JSON，使用自然的文本格式。""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 50,
        },
    ]

    for entry in designer_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )

    # 4. 创建 assistant > agent > writer 提示词链
    writer_chain_id = generate_id()
    writer_version_id = generate_id()
    writer_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": writer_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "writer",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": writer_version_id,
            "prompt_chain_id": writer_chain_id,
            "version_hash": writer_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "初始版本",
            "created_at": now,
        },
    )

    # Writer 提示词条目
    writer_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": writer_version_id,
            "name": "系统角色",
            "role": "system",
            "content": """你是一位优秀的小说作家，擅长创作引人入胜的故事内容。

你的任务是：
根据提供的大纲，撰写完整的章节内容。

写作要求：
1. 严格按照大纲的结构和情节点展开
2. 注意与前文的衔接和连贯性
3. 刻画生动的场景和人物
4. 使用恰当的描写手法（环境、心理、动作、对话等）
5. 保持合适的节奏和情感基调
6. 文笔流畅，语言优美""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": writer_version_id,
            "name": "输出格式",
            "role": "user",
            "content": """输出格式：
直接输出章节正文内容，不要包含标题、大纲等额外信息。""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 30,
        },
    ]

    for entry in writer_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )

    # 5. 创建 assistant > agent > reviewer 提示词链
    reviewer_chain_id = generate_id()
    reviewer_version_id = generate_id()
    reviewer_version_hash = generate_id()[:8]

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": reviewer_chain_id,
            "mode_name": "assistant",
            "task_name": "agent",
            "agent_name": "reviewer",
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": reviewer_version_id,
            "prompt_chain_id": reviewer_chain_id,
            "version_hash": reviewer_version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "初始版本",
            "created_at": now,
        },
    )

    # Reviewer 提示词条目
    reviewer_entries = [
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": reviewer_version_id,
            "name": "系统角色",
            "role": "system",
            "content": """你是一位严谨的编辑，擅长审查小说内容的质量和一致性。

你的任务是：
审查生成的章节内容，检查是否存在问题。

检查项：
1. 是否符合用户的原始请求
2. 是否与大纲一致
3. 是否与前文内容一致（人物、情节、设定等）
4. 是否存在剧情冲突或逻辑问题
5. 角色行为是否合理
6. 文笔和表达是否流畅""",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 150,
        },
        {
            "id": generate_id(),
            "uid": generate_id(),
            "version_id": reviewer_version_id,
            "name": "输出格式",
            "role": "user",
            "content": """输出格式（严格的JSON）：
{
    "passed": true/false,
    "feedback": "详细的反馈说明",
    "suggestions": ["建议1", "建议2", ...]
}

注意：
- 如果内容质量良好，没有明显问题，应该通过审查（passed: true）
- 只有在存在明显问题时才不通过（passed: false）
- feedback 应该具体指出问题所在
- suggestions 应该给出改进建议""",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 120,
        },
    ]

    for entry in reviewer_entries:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {**entry, "created_at": now, "updated_at": now},
        )


def downgrade() -> None:
    """Remove agent prompts and agent_session_id from tasks table."""
    # 删除 agent_session_id 字段
    op.drop_index("ix_tasks_agent_session_id", table_name="tasks")
    op.drop_column("tasks", "agent_session_id")

    # 删除 agent 提示词链
    conn = op.get_bind()
    
    # 删除所有 assistant > agent 的提示词链及其相关数据
    conn.execute(
        sa.text("""
            DELETE FROM prompt_entries 
            WHERE version_id IN (
                SELECT pv.id FROM prompt_chain_versions pv
                JOIN prompt_chains pc ON pv.prompt_chain_id = pc.id
                WHERE pc.mode_name = 'assistant' AND pc.task_name = 'agent'
            )
        """)
    )
    
    conn.execute(
        sa.text("""
            DELETE FROM prompt_chain_versions 
            WHERE prompt_chain_id IN (
                SELECT id FROM prompt_chains 
                WHERE mode_name = 'assistant' AND task_name = 'agent'
            )
        """)
    )
    
    conn.execute(
        sa.text("""
            DELETE FROM prompt_chains 
            WHERE mode_name = 'assistant' AND task_name = 'agent'
        """)
    )