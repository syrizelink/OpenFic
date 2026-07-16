# -*- coding: utf-8 -*-
"""Persistence 测试的数据库 fixture。

注意：此处刻意逐个导入具体模型而不使用 ``import app.storage.models``。
``app.storage.models.__init__`` 当前会触发 ``app.agent_runtime`` 包初始化，
后者与 ``app.audit.context`` 之间存在潜在循环导入；
通过仅导入用到的模型模块，可以避免该循环并保证 ``SQLModel.metadata``
中只注册测试需要的表。

由于顶层 conftest 已在 session 作用域调用 register_sqlmodel_models()，
SQLModel.metadata 全局单例中包含了所有模型。此处通过显式指定 tables 参数，
只为当前引擎创建测试需要的表。
"""

from collections.abc import AsyncGenerator, Callable
from typing import Any, cast

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.persistence.model import (
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
    _table(AgentContextCompaction),
    _table(AgentChildRun),
    _table(AgentChildRunRequest),
    _table(AgentDefinitionRecord),
    _table(PlanRecord),
    _table(PlanTodoRecord),
]


@pytest_asyncio.fixture
async def db_engine():
    """创建内存 SQLite 引擎并仅建所需表。"""
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
    """提供单一 AsyncSession 用于测试。"""
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
    """提供按需创建 AsyncSession 的工厂函数。"""
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
    """构造一个完整链路（项目 -> 章节 -> 任务）的测试样例。"""
    project = Project(id="proj_test", title="测试项目")
    volume = Volume(
        id="vol_test",
        project_id="proj_test",
        title="第一卷",
        order=1,
        chapter_count=1,
    )
    chapter = Chapter(
        id="chap_test",
        project_id="proj_test",
        volume_id="vol_test",
        title="测试章节",
        order=1,
    )
    task = Task(
        id="task_test",
        project_id="proj_test",
        title="测试任务",
        mode="agent",
        agent_session_id="session_test",
    )
    db_session.add(project)
    db_session.add(volume)
    db_session.add(chapter)
    db_session.add(task)
    await db_session.commit()
    return task
