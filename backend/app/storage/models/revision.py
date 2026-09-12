# -*- coding: utf-8 -*-
"""
Model data Revision - catatan versi tingkat proyek.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Revision(SQLModel, table=True):
    """
    Catatan versi tingkat proyek.

    Satu Revision mewakili satu putaran interaksi Agent yang dipicu pesan pengguna,
    dan bisa melibatkan nol sampai banyak perubahan bab (dicatat melalui Commits).

    Revision adalah titik versi bisnis yang terlihat pengguna; rollback membuat rollback revision baru,
    tanpa mengubah revision historis.
    """

    __tablename__ = "revisions"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")

    message: str = Field(description="Deskripsi versi/penjelasan operasi")
    agent_session_id: str | None = Field(
        default=None, description="ID sesi Agent yang terkait"
    )

    status: str = Field(
        default="active",
        index=True,
        description="Status Revision: active/interrupted/completed/failed/cancelled/rollback",
    )
    revision_type: str = Field(
        default="manual", index=True, description="Jenis Revision: agent/manual/rollback"
    )
    parent_revision_id: str | None = Field(
        default=None, index=True, foreign_key="revisions.id"
    )
    task_id: str | None = Field(
        default=None,
        sa_column=Column(
            String,
            ForeignKey("tasks.id", use_alter=True, name="fk_revisions_task_id_tasks"),
            nullable=True,
            index=True,
        ),
    )
    user_message_id: str | None = Field(
        default=None,
        index=True,
        description="ID pesan pengguna yang memicu revision ini",
    )
    user_message_seq: int | None = Field(
        default=None,
        index=True,
        description="seq pesan pengguna yang memicu revision ini",
    )
    pre_run_checkpoint_id: str | None = Field(
        default=None,
        index=True,
        description="checkpoint_id LangGraph sebelum pesan pengguna dikirim",
    )
    graph_thread_id: str | None = Field(
        default=None,
        index=True,
        description="LangGraph thread_id",
    )
    is_checkpoint: bool = Field(
        default=False, index=True, description="Apakah menjadi checkpoint yang terlihat pengguna"
    )

    project_snapshot_title: str = Field(max_length=200)
    project_snapshot_description: str | None = Field(default=None)
    project_snapshot_word_count: int = Field(default=0)
    project_snapshot_chapter_count: int = Field(default=0)

    started_at: datetime | None = Field(default=None, index=True)
    finished_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
