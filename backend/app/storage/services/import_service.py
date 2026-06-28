# -*- coding: utf-8 -*-
"""
Import Service - 导入业务逻辑层。
"""

from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import save_cover_file
from app.core.txt_parser import ParsedChapter
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.repos import project_repo
from app.storage.services import writing_activity_service
from app.storage.services.volume_service import DEFAULT_VOLUME_TITLE


@dataclass
class ImportResult:
    """导入结果。"""

    project_id: str
    title: str
    chapter_count: int
    total_word_count: int


async def confirm_import(
    session: AsyncSession,
    title: str,
    description: str | None,
    cover_file: UploadFile | None,
    chapters: list[ParsedChapter],
) -> ImportResult:
    """
    确认导入，创建项目和所有章节。

    Args:
        session: 数据库 session。
        title: 书名。
        description: 简介，可选。
        cover_file: 封面文件，可选。
        chapters: 解析后的章节列表。

    Returns:
        导入结果。
    """
    # 计算总字数
    total_word_count = sum(c.word_count for c in chapters)

    # 创建项目
    project = Project(
        title=title,
        description=description,
        word_count=total_word_count,
        chapter_count=len(chapters),
    )
    project = await project_repo.create(session, project)

    volume = Volume(
        project_id=project.id,
        title=DEFAULT_VOLUME_TITLE,
        description=None,
        order=1,
        chapter_count=len(chapters),
    )
    session.add(volume)
    await session.flush()

    # 如果提供了封面文件，保存封面
    if cover_file:
        cover_path = await save_cover_file(project.id, cover_file)
        project.cover_path = cover_path
        project = await project_repo.update(session, project)

    # 批量创建章节对象
    chapter_objects = [
        Chapter(
            project_id=project.id,
            volume_id=volume.id,
            title=parsed_chapter.title,
            content=parsed_chapter.content,
            word_count=parsed_chapter.word_count,
            order=order,
        )
        for order, parsed_chapter in enumerate(chapters, start=1)
    ]

    # 批量插入所有章节
    session.add_all(chapter_objects)
    await session.flush()

    for chapter in chapter_objects:
        await writing_activity_service.record_activity(
            session,
            project_id=project.id,
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            source="import",
            operation="import",
            old_word_count=0,
            new_word_count=chapter.word_count,
        )

    return ImportResult(
        project_id=project.id,
        title=project.title,
        chapter_count=len(chapters),
        total_word_count=total_word_count,
    )
