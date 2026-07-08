# -*- coding: utf-8 -*-
"""Skill Service - Skill 业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.storage.models.skill import Skill
from app.storage.repos import skill_reference_doc_repo, skill_repo


class SkillValidationError(Exception):
    """Skill 数据校验失败。"""


@dataclass
class SkillListResult:
    items: list[Skill]
    total: int
    page: int
    page_size: int


def is_skill_complete(skill: Skill) -> bool:
    return bool(skill.name.strip() and skill.summary.strip() and skill.content.strip())


async def _ensure_unique_name(session: AsyncSession, name: str) -> str:
    existing_names = {n for n in await skill_repo.get_all_names(session)}
    if name not in existing_names:
        return name
    base = name
    n = 2
    while f"{base} ({n})" in existing_names:
        n += 1
    return f"{base} ({n})"


async def create_skill(
    session: AsyncSession,
    *,
    name: str = "",
    summary: str = "",
    content: str = "",
    is_enabled: bool = False,
) -> Skill:
    unique_name = await _ensure_unique_name(session, name)
    skill = Skill(
        name=unique_name,
        summary=summary,
        content=content,
        is_enabled=is_enabled,
    )
    if skill.is_enabled and not is_skill_complete(skill):
        raise SkillValidationError("Skill 信息未完整填写，无法启用。")
    return await skill_repo.create(session, skill)


async def get_skill(session: AsyncSession, skill_db_id: str) -> Skill:
    skill = await skill_repo.get_by_id(session, skill_db_id)
    if skill is None:
        raise NotFoundError(f"Skill 不存在: {skill_db_id}")
    return skill


async def list_skills(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> SkillListResult:
    items, total = await skill_repo.get_all(session, page, page_size)
    return SkillListResult(items=items, total=total, page=page, page_size=page_size)


async def list_enabled_skills_by_ids(
    session: AsyncSession,
    ids: list[str],
) -> list[Skill]:
    if not ids:
        return []
    skills = await skill_repo.list_by_ids(session, ids)
    skill_by_id = {
        skill.id: skill
        for skill in skills
        if isinstance(skill.id, str) and skill.id and skill.is_enabled and is_skill_complete(skill)
    }
    return [skill_by_id[skill_id] for skill_id in ids if skill_id in skill_by_id]


async def update_skill(
    session: AsyncSession,
    skill_db_id: str,
    *,
    name: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    is_enabled: bool | None = None,
) -> Skill:
    skill = await get_skill(session, skill_db_id)

    if name is not None and name != skill.name:
        matches = await skill_repo.list_by_names(session, [name])
        if any(other.id != skill.id for other in matches):
            raise ConflictError(f"技能名称已存在: {name}")
        skill.name = name
    if summary is not None:
        skill.summary = summary
    if content is not None:
        skill.content = content
    if is_enabled is not None:
        skill.is_enabled = is_enabled

    if skill.is_enabled and not is_skill_complete(skill):
        raise SkillValidationError("Skill 信息未完整填写，无法启用。")

    skill.updated_at = datetime.now(UTC)
    return await skill_repo.update(session, skill)


async def toggle_skill(session: AsyncSession, skill_db_id: str) -> Skill:
    skill = await get_skill(session, skill_db_id)
    next_enabled = not skill.is_enabled
    if next_enabled and not is_skill_complete(skill):
        raise SkillValidationError("Skill 信息未完整填写，无法启用。")
    skill.is_enabled = next_enabled
    skill.updated_at = datetime.now(UTC)
    return await skill_repo.update(session, skill)


async def delete_skill(session: AsyncSession, skill_db_id: str) -> None:
    skill = await get_skill(session, skill_db_id)
    await skill_reference_doc_repo.delete_by_skill(session, skill_db_id)
    await skill_repo.delete(session, skill)
