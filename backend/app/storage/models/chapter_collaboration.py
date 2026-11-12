"""Durable Yjs identity and binary state for a chapter."""

from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class ChapterCollaboration(SQLModel, table=True):
    __tablename__ = "chapter_collaboration"

    chapter_id: str = Field(
        primary_key=True, foreign_key="chapters.id", ondelete="CASCADE"
    )
    epoch: str = Field(default_factory=generate_id)
    state: bytes | None = Field(
        default=None, sa_column=Column(LargeBinary, nullable=True)
    )
    version: int = Field(default=0)
