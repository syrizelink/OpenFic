"""Character graph persistence."""

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.character import CharacterRelationship


async def list_for_project(session: AsyncSession, project_id: str) -> list[CharacterRelationship]:
    result = await session.execute(select(CharacterRelationship).where(col(CharacterRelationship.project_id) == project_id))
    return list(result.scalars().all())


async def get(session: AsyncSession, relationship_id: str) -> CharacterRelationship | None:
    return await session.get(CharacterRelationship, relationship_id)


async def get_pair(session: AsyncSession, project_id: str, source: str, target: str) -> CharacterRelationship | None:
    result = await session.execute(select(CharacterRelationship).where(
        col(CharacterRelationship.project_id) == project_id,
        col(CharacterRelationship.source_character_id) == source,
        col(CharacterRelationship.target_character_id) == target,
    ))
    return result.scalar_one_or_none()


async def remove_for_characters(session: AsyncSession, project_id: str, ids: list[str]) -> None:
    if ids:
        await session.execute(delete(CharacterRelationship).where(
            col(CharacterRelationship.project_id) == project_id,
            or_(col(CharacterRelationship.source_character_id).in_(ids), col(CharacterRelationship.target_character_id).in_(ids)),
        ))


async def remove_for_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(delete(CharacterRelationship).where(col(CharacterRelationship.project_id) == project_id))
