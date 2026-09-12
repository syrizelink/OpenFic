# -*- coding: utf-8 -*-
"""Fixture basis data untuk uji Persistence.

Catatan: di sini model diimpor satu per satu secara sengaja, bukan lewat ``import app.storage.models``.
``app.storage.models.__init__`` saat ini memicu inisialisasi paket ``app.agent_runtime``,
dan paket itu berpotensi impor sirkular dengan ``app.audit.context``;
dengan hanya mengimpor modul model yang dipakai, siklus itu dihindari dan ``SQLModel.metadata``
hanya memuat tabel yang dibutuhkan uji.

Karena conftest tingkat atas sudah memanggil register_sqlmodel_models() pada scope session,
singleton global SQLModel.metadata memuat semua model. Di sini parameter tables ditentukan eksplisit
agar hanya tabel yang dibutuhkan uji dibuat untuk engine ini.
"""

from collections.abc import AsyncGenerator, Callable
from typing import Any, cast

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.persistence.model import (
    AgentAttachment,
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentDefinitionRecord,
    AgentRunMessage,
    PlanRecord,
    PlanTodoRecord,
)
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume

def _table(model: Any) -> Any:
    return getattr(model, "__table__")


_PERSISTENCE_TABLES = [
    _table(Project),
    _table(Volume),
    _table(Chapter),
    _table(Task),
    _table(AgentRunMessage),
    _table(AgentAttachment),
    _table(AgentContextCompaction),
    _table(AgentChildRun),
    _table(AgentChildRunRequest),
    _table(AgentDefinitionRecord),
    _table(PlanRecord),
    _table(PlanTodoRecord),
]


@pytest_asyncio.fixture
async def db_engine():
    """Membuat engine SQLite in-memory dan hanya membuat tabel yang diperlukan."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=_PERSISTENCE_TABLES,
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Menyediakan satu AsyncSession untuk uji."""
    factory = cast(
        Callable[[], AsyncSession],
        sessionmaker(  # type: ignore[call-overload]
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def db_session_factory(db_engine) -> Callable[[], AsyncSession]:
    """Menyediakan fungsi factory untuk membuat AsyncSession sesuai kebutuhan."""
    factory = cast(
        Callable[[], AsyncSession],
        sessionmaker(  # type: ignore[call-overload]
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )

    def make() -> AsyncSession:
        return factory()

    return make


@pytest_asyncio.fixture
async def sample_task(db_session: AsyncSession) -> Task:
    """Menyusun contoh uji dengan rantai lengkap (proyek -> bab -> tugas)."""
    project = Project(id="proj_test", title="Proyek Uji")
    volume = Volume(
        id="vol_test",
        project_id="proj_test",
        title="Volume 1",
        order=1,
        chapter_count=1,
    )
    chapter = Chapter(
        id="chap_test",
        project_id="proj_test",
        volume_id="vol_test",
        title="Bab Uji",
        order=1,
    )
    task = Task(
        id="task_test",
        project_id="proj_test",
        title="Tugas Uji",
        mode="agent",
        agent_session_id="session_test",
    )
    db_session.add(project)
    db_session.add(volume)
    db_session.add(chapter)
    db_session.add(task)
    await db_session.commit()
    return task
