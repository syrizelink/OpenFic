# -*- coding: utf-8 -*-
"""
Commit 数据模型 - 章节级变更记录。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Commit(SQLModel, table=True):
    """
    章节级变更记录。

    一个 Commit 记录单个章节在某个 Revision 中的具体变更。

    Attributes:
        id: 变更唯一标识符（nanoid）。
        revision_id: 所属版本 ID。
        chapter_id: 章节 ID。
        operation: 操作类型（create/update/delete）。
        snapshot_title: 变更前的标题。
        snapshot_content: 变更前的内容。
        snapshot_word_count: 变更前的字数。
        snapshot_order: 变更前的排序。
        new_title: 变更后的标题。
        new_content: 变更后的内容。
        new_word_count: 变更后的字数。
        new_order: 变更后的排序。
        created_at: 创建时间。
    """

    __tablename__ = "commits"

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    chapter_id: str = Field(index=True, foreign_key="chapters.id")

    # 变更类型：create, update, delete
    operation: str = Field(max_length=20, description="操作类型: create/update/delete")

    # 快照数据（存储变更前的状态）
    snapshot_title: str | None = Field(default=None, max_length=200)
    snapshot_content: str | None = Field(default=None)
    snapshot_word_count: int | None = Field(default=None)
    snapshot_order: int | None = Field(default=None)

    # 变更后的数据（用于 redo 或查看变更）
    new_title: str | None = Field(default=None, max_length=200)
    new_content: str | None = Field(default=None)
    new_word_count: int | None = Field(default=None)
    new_order: int | None = Field(default=None)

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))