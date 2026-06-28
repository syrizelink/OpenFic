# -*- coding: utf-8 -*-
"""
Note 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class NoteCategory(SQLModel, table=True):
    __tablename__ = "note_categories"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    parent_id: str | None = Field(
        default=None,
        index=True,
        foreign_key="note_categories.id",
    )
    title: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    category_id: str | None = Field(
        default=None,
        index=True,
        foreign_key="note_categories.id",
    )
    title: str = Field(max_length=200)
    content: str = Field(default="")
    is_locked: bool = Field(default=False)
    is_hidden: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
