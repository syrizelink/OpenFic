# -*- coding: utf-8 -*-
"""
PromptChainVersion 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


def generate_short_hash() -> str:
    """生成8位短hash作为版本标识。"""
    return generate_id()[:8]


class PromptChainVersion(SQLModel, table=True):
    """
    提示词链版本模型。

    Attributes:
        id: 唯一标识符（nanoid）。
        mode_name: 模式名称（第一级导航）。
        task_name: 任务名称（第二级导航）。
        agent_name: Agent名称（第三级导航，可选）。
        version_hash: 版本短hash（8位，用于用户标识）。
        version_number: 语义版本号（v1, v2, v3...）。
        parent_version_id: 父版本ID（可选，用于追踪版本关系）。
        is_active: 是否在当前活跃分支上。
        note: 版本备注（可选）。
        created_at: 创建时间。
    """

    __tablename__ = "prompt_chain_versions"

    id: str = Field(default_factory=generate_id, primary_key=True)
    mode_name: str = Field(max_length=100, description="模式名称")
    task_name: str = Field(max_length=100, description="任务名称")
    agent_name: str | None = Field(default=None, max_length=100, description="Agent名称")
    version_hash: str = Field(default_factory=generate_short_hash, max_length=8, unique=True)
    version_number: int = Field(description="语义版本号")
    parent_version_id: str | None = Field(default=None, foreign_key="prompt_chain_versions.id")
    is_active: bool = Field(default=True, description="是否在当前活跃分支上")
    note: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
