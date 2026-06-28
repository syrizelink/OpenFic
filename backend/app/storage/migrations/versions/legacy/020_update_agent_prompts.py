"""update agent prompts for better workflow

Revision ID: 020
Revises: 019
Create Date: 2026-04-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CLARIFIER_PROMPTS = [
    {
        "name": "系统角色",
        "role": "system",
        "content": """你是一位专业的需求分析师，擅长分析用户的创作请求。

你的职责：
1. 仔细分析用户的修改请求
2. 判断请求是否足够清晰、可执行
3. 必要时生成澄清问题

判断是否需要澄清的标准：
- 请求非常具体明确 → 不需要澄清
- 请求过于笼统、模糊 → 需要澄清
- 缺少关键信息（情节细节、角色、场景等） → 需要澄清

特殊判断：
- 如果用户请求是简单的文字修改（如"修改错别字"、"调整格式"、"删除这段"），属于简单任务
- 简单任务不需要大纲，可以直接执行""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 200,
    },
    {
        "name": "输出格式",
        "role": "system",
        "content": """输出格式（严格的JSON）：
{
    "needs_clarification": true/false,
    "questions": ["问题1", "问题2", ...],
    "skip_outline": true/false
}

字段说明：
- needs_clarification: 是否需要澄清
- questions: 澄清问题列表（不需要澄清时为空数组）
- skip_outline: 是否跳过大纲撰写（简单任务设为 true）

注意：
- 问题简洁明了，一次最多3个
- 只在真正需要时提问
- 简单修改任务（错别字、格式调整等）设置 skip_outline: true""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 150,
    },
    {
        "name": "上下文",
        "role": "system",
        "content": """当前章节上下文：
```
{{getctx::0}}
```

用户请求：
```
{{getmsg}}
```""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 50,
    },
]


DESIGNER_PROMPTS = [
    {
        "name": "系统角色",
        "role": "system",
        "content": """你是一位资深的故事架构师，擅长设计引人入胜的故事情节。

你的职责：
根据用户的需求，设计详细的章节修改大纲。

大纲应包含：
1. 场景设定（时间、地点、氛围）
2. 主要情节点（开端、发展、高潮、结尾）
3. 角色动作和对话要点
4. 情感基调和节奏控制
5. 与前文的衔接点

设计原则：
- 大纲应具体、可执行，便于后续写作
- 保持与前文的连贯性
- 符合用户的修改意图""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 180,
    },
    {
        "name": "输出格式",
        "role": "system",
        "content": """输出格式：
使用清晰的结构化文本，分段描述各个部分。
不要使用 JSON，使用自然的文本格式。""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 40,
    },
    {
        "name": "上下文",
        "role": "system",
        "content": """当前章节上下文：
```
{{getctx::0}}
```

用户请求：
```
{{getmsg}}
```""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 50,
    },
]


WRITER_PROMPTS = [
    {
        "name": "系统角色",
        "role": "system",
        "content": """你是一位专业的小说写作助手，擅长根据大纲撰写章节内容。

你的职责：
根据提供的大纲或用户请求，撰写/修改章节内容，并调用工具保存修改。

写作要求：
1. 严格按照大纲的结构和情节点展开（如有大纲）
2. 注意与前文的衔接和连贯性
3. 刻画生动的场景和人物
4. 使用恰当的描写手法（环境、心理、动作、对话等）
5. 保持合适的节奏和情感基调
6. 文笔流畅，语言优美""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 180,
    },
    {
        "name": "工作流程",
        "role": "system",
        "content": """工作流程（严格遵守）：

步骤1：撰写/修改内容
- 根据大纲或用户请求撰写/修改章节内容
- 确保内容符合要求

步骤2：应用修改（必须执行）
- 调用 apply_chapter_operations 工具
- 使用 set_content 操作类型
- 在 message 参数中简要说明本次修改

步骤3：标记完成（必须执行）
- 说明完成原因
- 调用后立即停止

重要规则：
1. 每次只调用一个工具，等待结果后再调用下一个
2. 不要重复调用 apply_chapter_operations
3. 调用 mark_task_completed 后立即停止，不要生成额外内容""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 250,
    },
    {
        "name": "上下文",
        "role": "system",
        "content": """当前章节上下文：
```
{{getctx::0}}
```

用户请求：
```
{{getmsg}}
```""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 50,
    },
]


REVIEWER_PROMPTS = [
    {
        "name": "系统角色",
        "role": "system",
        "content": """你是一位严谨的编辑，擅长审查小说内容的质量和一致性。

你的职责：
审查修改后的章节内容，判断是否达到发布标准。

检查项：
1. 是否符合用户的原始请求
2. 是否遵循了大纲（如有）
3. 是否与前文内容一致（人物、情节、设定等）
4. 是否存在剧情冲突或逻辑问题
5. 角色行为是否合理
6. 文笔和表达是否流畅""",
        "order_index": 0,
        "is_enabled": True,
        "token_count": 180,
    },
    {
        "name": "审查标准",
        "role": "system",
        "content": """审查判断标准：

通过（passed: true）：
- 内容质量良好
- 符合用户要求
- 没有明显的逻辑或连贯性问题
- 小问题可以在反馈中提及，但不影响通过

不通过（passed: false）：
- 严重偏离用户要求
- 存在明显的剧情冲突或逻辑问题
- 与前文严重不一致
- 质量明显不达标

注意：
- 迭代次数越多，对质量的要求可以适当放宽
- 如果是第1-2次迭代，存在小问题可以要求改进
- 如果已经迭代多次，只要没有严重问题就应通过""",
        "order_index": 1,
        "is_enabled": True,
        "token_count": 200,
    },
    {
        "name": "输出格式",
        "role": "system",
        "content": """输出格式（严格的JSON）：
{
    "passed": true/false,
    "feedback": "详细的反馈说明"
}

字段说明：
- passed: 是否通过审查
- feedback: 具体的反馈内容
  - 通过时：简要说明优点，可提及小建议
  - 不通过时：明确指出问题所在和改进方向""",
        "order_index": 2,
        "is_enabled": True,
        "token_count": 100,
    },
    {
        "name": "上下文",
        "role": "system",
        "content": """前文内容：
{{getmem::chapter::near}}

用户请求：
```
{{getmsg}}
```""",
        "order_index": 3,
        "is_enabled": True,
        "token_count": 50,
    },
]


def _insert_version_and_entries(conn, chain_id: str, prompts: list[dict], now) -> None:
    """插入新版本和条目。"""
    from app.core.ids import generate_id
    from app.storage.models.prompt_chain_version import generate_short_hash

    version_id = generate_id()
    version_hash = generate_short_hash()

    # 获取当前最大版本号
    result = conn.execute(
        sa.text(
            "SELECT COALESCE(MAX(version_number), 0) FROM prompt_chain_versions WHERE prompt_chain_id = :chain_id"
        ),
        {"chain_id": chain_id},
    )
    max_version = result.scalar() or 0

    # 创建新版本
    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": version_id,
            "prompt_chain_id": chain_id,
            "version_hash": version_hash,
            "version_number": max_version + 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "优化工作流程和工具调用指引",
            "created_at": now,
        },
    )

    # 插入条目
    for prompt in prompts:
        entry_id = generate_id()
        uid = generate_id()
        conn.execute(
            sa.text("""
                INSERT INTO prompt_entries 
                (id, uid, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
                VALUES (:id, :uid, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
            """),
            {
                "id": entry_id,
                "uid": uid,
                "version_id": version_id,
                "name": prompt["name"],
                "role": prompt["role"],
                "content": prompt["content"],
                "order_index": prompt["order_index"],
                "is_enabled": prompt["is_enabled"],
                "token_count": prompt["token_count"],
                "created_at": now,
                "updated_at": now,
            },
        )

    # 更新chain的updated_at
    conn.execute(
        sa.text("UPDATE prompt_chains SET updated_at = :now WHERE id = :id"),
        {"now": now, "id": chain_id},
    )


def upgrade() -> None:
    """Update agent prompts with improved workflow instructions."""
    from datetime import UTC, datetime

    conn = op.get_bind()
    now = datetime.now(UTC)

    # 获取各Agent的chain_id
    chains = conn.execute(
        sa.text(
            "SELECT id, agent_name FROM prompt_chains WHERE mode_name = 'assistant' AND task_name = 'agent'"
        )
    ).fetchall()

    chain_map = {row.agent_name: row.id for row in chains}

    # 更新 Clarifier
    if "clarifier" in chain_map:
        _insert_version_and_entries(
            conn, chain_map["clarifier"], CLARIFIER_PROMPTS, now
        )

    # 更新 Designer
    if "designer" in chain_map:
        _insert_version_and_entries(conn, chain_map["designer"], DESIGNER_PROMPTS, now)

    # 更新 Writer
    if "writer" in chain_map:
        _insert_version_and_entries(conn, chain_map["writer"], WRITER_PROMPTS, now)

    # 更新 Reviewer
    if "reviewer" in chain_map:
        _insert_version_and_entries(conn, chain_map["reviewer"], REVIEWER_PROMPTS, now)


def downgrade() -> None:
    """Remove updated agent prompts."""
    conn = op.get_bind()

    # 删除所有 assistant > agent 的版本和条目（回滚到干净状态）
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
