# -*- coding: utf-8 -*-
"""Character 数据模型。"""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Character(SQLModel, table=True):
    """项目角色模型。"""

    __tablename__ = "characters"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    name: str = Field(max_length=200)
    description: str = Field(default="")
    image_path: str | None = Field(default=None)
    is_favorited: bool = Field(default=False, index=True)
    graph_x: float | None = Field(default=None)
    graph_y: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class CharacterRelationship(SQLModel, table=True):
    __tablename__ = "character_relationships"
    __table_args__ = (
        UniqueConstraint("project_id", "source_character_id", "target_character_id"),
        CheckConstraint("source_character_id < target_character_id"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    source_character_id: str = Field(index=True, foreign_key="characters.id")
    target_character_id: str = Field(index=True, foreign_key="characters.id")
    name: str = Field(max_length=200)
    description: str = Field(default="")


class RevisionCharacterRelationshipSnapshot(SQLModel, table=True):
    __tablename__ = "revision_character_relationship_snapshots"
    __table_args__ = (UniqueConstraint("revision_id", "relationship_id"),)

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    relationship_id: str = Field(index=True)
    project_id: str = Field(index=True)
    exists: bool
    source_character_id: str | None = None
    target_character_id: str | None = None
    name: str | None = None
    description: str | None = None
