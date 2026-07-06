# -*- coding: utf-8 -*-
"""Character Service - 角色业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime

import tiktoken
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.storage import delete_character_image, save_character_image
from app.storage.models.character import Character
from app.storage.repos import character_repo, project_repo


@dataclass
class CharacterListResult:
    """角色列表结果。"""

    items: list[Character]
    total: int
    page: int
    page_size: int


@dataclass
class CharacterSearchMatch:
    """角色搜索匹配项。"""

    line_number: int
    line_text: str


@dataclass
class CharacterSearchResult:
    """单个角色搜索结果。"""

    character_id: str
    character_name: str
    matches: list[CharacterSearchMatch]


@dataclass
class CharacterSearchResponse:
    """角色搜索结果。"""

    results: list[CharacterSearchResult]
    total_characters: int
    total_matches: int


def make_available_name(base_name: str, existing_names: list[str]) -> str:
    """生成同项目下可用角色名。"""
    existing = set(existing_names)
    if base_name not in existing:
        return base_name

    index = 2
    while f"{base_name} ({index})" in existing:
        index += 1
    return f"{base_name} ({index})"


def calculate_token_count(content: str) -> int:
    """计算文本 Token 数。"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(content))
    except Exception:
        return len(content) // 2


async def create_character(
    session: AsyncSession,
    project_id: str,
    name: str,
    description: str = "",
    image_file: UploadFile | None = None,
) -> Character:
    """创建角色。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    resolved_name = make_available_name(name.strip(), await character_repo.list_names_by_project(session, project_id))

    character = await character_repo.create(
        session,
        Character(project_id=project_id, name=resolved_name, description=description),
    )
    if image_file is not None:
        character.image_path = await save_character_image(character.id, image_file)
        character.updated_at = datetime.now(UTC)
        character = await character_repo.update(session, character)
    return character


async def get_character(session: AsyncSession, character_id: str) -> Character:
    """获取角色。"""
    character = await character_repo.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError(f"角色不存在: {character_id}")
    return character


async def list_characters_by_project(
    session: AsyncSession,
    project_id: str,
    page: int = 1,
    page_size: int = 50,
) -> CharacterListResult:
    """按项目获取角色列表。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    items, total = await character_repo.list_by_project(session, project_id, page, page_size)
    return CharacterListResult(items=items, total=total, page=page, page_size=page_size)


async def search_characters(
    session: AsyncSession,
    project_id: str,
    query: str,
) -> CharacterSearchResponse:
    """搜索项目角色名称和描述。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    stripped_query = query.strip()
    if not stripped_query:
        return CharacterSearchResponse(results=[], total_characters=0, total_matches=0)

    characters = await character_repo.search_by_project(session, project_id, stripped_query)
    lower_query = stripped_query.lower()
    results: list[CharacterSearchResult] = []
    total_matches = 0

    for character in characters:
        matches: list[CharacterSearchMatch] = []
        for line_number, line in enumerate(character.description.split("\n"), start=1):
            if lower_query in line.lower():
                matches.append(CharacterSearchMatch(line_number=line_number, line_text=line))

        if lower_query in character.name.lower():
            matches.insert(0, CharacterSearchMatch(line_number=0, line_text=character.name))

        if matches:
            results.append(
                CharacterSearchResult(
                    character_id=character.id,
                    character_name=character.name,
                    matches=matches,
                )
            )
            total_matches += len(matches)

    return CharacterSearchResponse(
        results=results,
        total_characters=len(results),
        total_matches=total_matches,
    )


async def update_character(
    session: AsyncSession,
    character_id: str,
    name: str | None = None,
    description: str | None = None,
    is_favorited: bool | None = None,
    image_file: UploadFile | None = None,
) -> Character:
    """更新角色。"""
    character = await get_character(session, character_id)
    old_image_path = character.image_path

    if name is not None:
        next_name = name.strip()
        if await character_repo.name_exists(session, character.project_id, next_name, exclude_character_id=character.id):
            raise ConflictError("角色名称已存在")
        character.name = next_name
    if description is not None:
        character.description = description
    if is_favorited is not None:
        character.is_favorited = is_favorited
    if image_file is not None:
        character.image_path = await save_character_image(character.id, image_file)
    character.updated_at = datetime.now(UTC)
    character = await character_repo.update(session, character)

    if image_file is not None and old_image_path:
        delete_character_image(old_image_path)
    return character


async def delete_character(session: AsyncSession, character_id: str) -> None:
    """删除角色。"""
    character = await get_character(session, character_id)
    image_path = character.image_path
    await character_repo.delete(session, character)
    if image_path:
        delete_character_image(image_path)


async def batch_update_favorite(
    session: AsyncSession,
    project_id: str,
    character_ids: list[str],
    is_favorited: bool,
) -> int:
    """批量更新角色收藏状态。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    return await character_repo.batch_update_favorite(session, project_id, character_ids, is_favorited)


async def batch_delete_characters(
    session: AsyncSession,
    project_id: str,
    character_ids: list[str],
) -> int:
    """批量删除角色。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    characters = await character_repo.list_by_project_and_ids(session, project_id, character_ids)
    deleted_count = await character_repo.batch_delete(session, project_id, character_ids)
    for character in characters:
        if character.image_path:
            delete_character_image(character.image_path)
    return deleted_count
