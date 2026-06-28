# -*- coding: utf-8 -*-
"""
PromptEntry 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class PromptEntry(SQLModel, table=True):
    """
    提示词条目模型（版本化内容）。

    Attributes:
        id: 唯一标识符（nanoid）。
        uid: 跨版本追踪标识符（UUID）- 用于识别同一条目在不同版本中的变化。
        version_id: 所属版本ID。
        name: 条目名称。
        role: 角色类型（system/user/assistant）。
        content: 提示词内容（包含宏的原始文本）。
        order_index: 排序索引。
        is_enabled: 是否启用。
        token_count: Token计数。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "prompt_entries"

    id: str = Field(default_factory=generate_id, primary_key=True)
    uid: str = Field(index=True, description="跨版本追踪标识符")
    version_id: str = Field(foreign_key="prompt_chain_versions.id")
    name: str = Field(max_length=200)
    role: str = Field(max_length=20, description="system/user/assistant")
    content: str = Field(description="提示词内容")
    order_index: int = Field(description="排序索引")
    is_enabled: bool = Field(default=True, description="是否启用")
    token_count: int = Field(default=0, description="Token计数")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
