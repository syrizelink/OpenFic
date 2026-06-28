# -*- coding: utf-8 -*-
"""getworld 宏编译测试。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.macro.compiler import EntryInput, PromptChainCompiler
from app.storage.models.project import Project
from app.storage.models.world_info import WorldInfo
from app.storage.models.world_info_entry import WorldInfoEntry


@pytest.mark.asyncio
async def test_getworld_injects_all_enabled_entries(
    session: AsyncSession,
) -> None:
    """getworld 应注入所有启用的条目，禁用条目不注入。"""
    project = Project(id="project-world", title="世界书项目")
    world_info = WorldInfo(id="world-info", project_id=project.id, name="主世界书")
    session.add(project)
    session.add(world_info)
    session.add_all(
        [
            WorldInfoEntry(
                world_info_id=world_info.id,
                uid=1,
                name="世界规则",
                order=1,
                content="不可违背的常驻设定",
            ),
            WorldInfoEntry(
                world_info_id=world_info.id,
                uid=2,
                name="雾港",
                order=2,
                content="雾港终年有雾",
            ),
            WorldInfoEntry(
                world_info_id=world_info.id,
                uid=3,
                name="未启用",
                order=3,
                content="不应出现",
                is_enabled=False,
            ),
        ]
    )
    await session.commit()

    compiler = PromptChainCompiler(session)
    result = await compiler.compile(
        entries=[
            EntryInput(
                role="system",
                content="世界书:\n{{getworld}}",
                order_index=1,
                is_enabled=True,
            )
        ],
        project_id=project.id,
    )

    compiled = result.entries[0].content
    assert compiled == (
        "世界书:\n"
        "<世界规则>\n"
        "不可违背的常驻设定\n"
        "</世界规则>\n"
        "<雾港>\n"
        "雾港终年有雾\n"
        "</雾港>"
    )


@pytest.mark.asyncio
async def test_getworld_escapes_entry_content(session: AsyncSession) -> None:
    """getworld 输出应转义条目内容中的 XML 特殊字符。"""
    project = Project(id="project-escape", title="转义项目")
    world_info = WorldInfo(id="world-escape", project_id=project.id, name="转义世界书")
    session.add(project)
    session.add(world_info)
    session.add(
        WorldInfoEntry(
            world_info_id=world_info.id,
            uid=1,
            name="规则",
            order=1,
            content="A < B & C > D",
        )
    )
    await session.commit()

    compiler = PromptChainCompiler(session)
    result = await compiler.compile(
        entries=[
            EntryInput(
                role="system",
                content="{{getworld}}",
                order_index=1,
                is_enabled=True,
            )
        ],
        project_id=project.id,
    )

    assert result.entries[0].content == "<规则>\nA &lt; B &amp; C &gt; D\n</规则>"


@pytest.mark.asyncio
async def test_getworld_sorts_selected_entries_by_order(session: AsyncSession) -> None:
    """getworld 注入顺序应跟随世界书 order，而不是插入顺序。"""
    project = Project(id="project-world-order", title="排序项目")
    world_info = WorldInfo(id="world-order", project_id=project.id, name="排序世界书")
    session.add(project)
    session.add(world_info)
    session.add_all(
        [
            WorldInfoEntry(
                world_info_id=world_info.id,
                uid=2,
                name="乙",
                order=2,
                content="乙内容",
            ),
            WorldInfoEntry(
                world_info_id=world_info.id,
                uid=1,
                name="甲",
                order=1,
                content="甲内容",
            ),
        ]
    )
    await session.commit()

    compiler = PromptChainCompiler(session)
    result = await compiler.compile(
        entries=[
            EntryInput(
                role="system",
                content="{{getworld}}",
                order_index=1,
                is_enabled=True,
            )
        ],
        project_id=project.id,
    )

    assert result.entries[0].content == "<甲>\n甲内容\n</甲>\n<乙>\n乙内容\n</乙>"
