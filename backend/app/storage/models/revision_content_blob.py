# -*- coding: utf-8 -*-
"""Content-addressed blob storage for revision/commit large text payloads."""

from datetime import UTC, datetime

from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel


class RevisionContentBlob(SQLModel, table=True):
    """Deduplicated, compressed text content referenced by revisions and commits.

    ``id`` is the sha256 hex digest of the raw UTF-8 text, so identical content
    is stored exactly once regardless of how many revisions/commits reference it.
    ``data`` holds the zlib-compressed raw text.
    """

    __tablename__ = "revision_content_blobs"

    id: str = Field(primary_key=True, description="sha256 hex of raw UTF-8 text")
    data: bytes = Field(
        sa_column=Column(LargeBinary), description="zlib-compressed raw text"
    )
    raw_size: int = Field(description="size in bytes of the uncompressed text")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="when the blob was first stored",
    )
