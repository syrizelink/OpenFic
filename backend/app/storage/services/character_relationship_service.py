"""Project-scoped character relationships and graph traversal."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.storage.models.character import CharacterRelationship
from app.storage.repos import character_repo, character_relationship_repo, project_repo


async def list_for_project(session: AsyncSession, project_id: str) -> list[CharacterRelationship]:
    if await project_repo.get_by_id(session, project_id) is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    return await character_relationship_repo.list_for_project(session, project_id)


async def create_relationship(session: AsyncSession, project_id: str, source: str, target: str, name: str, description: str = "") -> CharacterRelationship:
    if source == target:
        raise ValueError("不能建立角色与自身的关系")
    normalized = name.strip()
    if not normalized or len(normalized) > 200:
        raise ValueError("关系名称长度须为 1 到 200 字符")
    if len(description) > 10000:
        raise ValueError("关系说明不能超过 10000 字符")
    if await project_repo.get_by_id(session, project_id) is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    characters = await character_repo.list_by_project_and_ids(session, project_id, [source, target])
    if len(characters) != 2:
        raise NotFoundError("角色不存在于当前项目")
    source, target = sorted((source, target))
    if await character_relationship_repo.get_pair(session, project_id, source, target):
        raise ConflictError("这两个角色已有关系")
    relation = CharacterRelationship(project_id=project_id, source_character_id=source, target_character_id=target, name=normalized, description=description)
    session.add(relation)
    await session.flush()
    return relation


async def get_relationship(session: AsyncSession, relationship_id: str) -> CharacterRelationship:
    relation = await character_relationship_repo.get(session, relationship_id)
    if relation is None:
        raise NotFoundError("关系不存在")
    return relation


async def update_relationship(session: AsyncSession, relationship_id: str, name: str, description: str) -> CharacterRelationship:
    relation = await get_relationship(session, relationship_id)
    normalized = name.strip()
    if not normalized or len(normalized) > 200 or len(description) > 10000:
        raise ValueError("关系名称或说明超出限制")
    relation.name = normalized
    relation.description = description
    await session.flush()
    return relation


async def delete_relationship(session: AsyncSession, relationship_id: str) -> None:
    relation = await get_relationship(session, relationship_id)
    await session.delete(relation)
    await session.flush()


async def set_position(session: AsyncSession, project_id: str, character_id: str, x: float, y: float) -> None:
    character = await character_repo.get_by_id(session, character_id)
    if character is None or character.project_id != project_id:
        raise NotFoundError("角色不存在于当前项目")
    character.graph_x, character.graph_y = x, y
    await session.flush()
