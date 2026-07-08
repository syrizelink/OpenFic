# -*- coding: utf-8 -*-
"""SkillReferenceDoc Repository - 参考文档数据访问层。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.skill_reference_doc import SkillReferenceDoc


async def create(session: AsyncSession, doc: SkillReferenceDoc) -> SkillReferenceDoc:
    session.add(doc)
    await session.flush()
    await session.refresh(doc)
    return doc


async def get_by_id(session: AsyncSession, doc_id: str) -> SkillReferenceDoc | None:
    result = await session.execute(
        select(SkillReferenceDoc).where(col(SkillReferenceDoc.id) == doc_id)
    )
    return result.scalar_one_or_none()


async def list_by_skill(session: AsyncSession, skill_db_id: str) -> list[SkillReferenceDoc]:
    result = await session.execute(
        select(SkillReferenceDoc)
        .where(col(SkillReferenceDoc.skill_db_id) == skill_db_id)
        .order_by(col(SkillReferenceDoc.created_at).asc(), col(SkillReferenceDoc.id).asc())
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, doc: SkillReferenceDoc) -> SkillReferenceDoc:
    session.add(doc)
    await session.flush()
    await session.refresh(doc)
    return doc


async def delete(session: AsyncSession, doc: SkillReferenceDoc) -> None:
    await session.delete(doc)
    await session.flush()


async def delete_by_skill(session: AsyncSession, skill_db_id: str) -> None:
    result = await session.execute(
        select(SkillReferenceDoc).where(col(SkillReferenceDoc.skill_db_id) == skill_db_id)
    )
    for doc in result.scalars().all():
        await session.delete(doc)
    await session.flush()
