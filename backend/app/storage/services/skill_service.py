# -*- coding: utf-8 -*-
"""Skill Service - Skill 业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.skill import Skill
from app.storage.repos import skill_repo

SKILL_ID_PATTERN = re.compile(r"^[a-z]+(?:-[a-z]+)*$")


class SkillValidationError(Exception):
    """Skill 数据校验失败。"""


class SkillIdConflictError(Exception):
    """Skill ID 冲突。"""


@dataclass
class SkillListResult:
    items: list[Skill]
    total: int
    page: int
    page_size: int


def normalize_skill_id(skill_id: str) -> str:
    return skill_id.strip()


def is_skill_complete(skill: Skill) -> bool:
    return bool(
        skill.name.strip()
        and skill.summary.strip()
        and skill.skill_id.strip()
        and skill.content.strip()
        and SKILL_ID_PATTERN.fullmatch(skill.skill_id.strip())
    )


def validate_skill_id(skill_id: str) -> None:
    normalized = normalize_skill_id(skill_id)
    if not normalized:
        return
    if not SKILL_ID_PATTERN.fullmatch(normalized):
        raise SkillValidationError("Skill ID 只允许英文小写字母和 '-'。")


async def create_skill(
    session: AsyncSession,
    *,
    name: str = "",
    summary: str = "",
    skill_id: str = "",
    content: str = "",
    is_enabled: bool = False,
) -> Skill:
    validate_skill_id(skill_id)

    normalized_id = normalize_skill_id(skill_id)
    if normalized_id:
        existing = await skill_repo.get_by_skill_id(session, normalized_id)
        if existing is not None:
            raise SkillIdConflictError(f"Skill ID 已存在: {skill_id}")

    skill = Skill(
        name=name,
        summary=summary,
        skill_id=normalized_id,
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


async def list_enabled_skills_by_skill_ids(
    session: AsyncSession,
    skill_ids: list[str],
) -> list[Skill]:
    if not skill_ids:
        return []
    skills = await skill_repo.list_by_skill_ids(session, skill_ids)
    skill_by_id = {
        skill.skill_id: skill
        for skill in skills
        if isinstance(skill.skill_id, str) and skill.skill_id and skill.is_enabled and is_skill_complete(skill)
    }
    return [skill_by_id[skill_id] for skill_id in skill_ids if skill_id in skill_by_id]


async def list_skills_by_skill_ids(session: AsyncSession, skill_ids: list[str]) -> list[Skill]:
    if not skill_ids:
        return []
    skills = await skill_repo.list_by_skill_ids(session, skill_ids)
    skill_by_id = {
        skill.skill_id: skill
        for skill in skills
        if isinstance(skill.skill_id, str) and skill.skill_id
    }
    return [skill_by_id[skill_id] for skill_id in skill_ids if skill_id in skill_by_id]


async def update_skill(
    session: AsyncSession,
    skill_db_id: str,
    *,
    name: str | None = None,
    summary: str | None = None,
    skill_id: str | None = None,
    content: str | None = None,
    is_enabled: bool | None = None,
) -> Skill:
    skill = await get_skill(session, skill_db_id)

    if name is not None:
        skill.name = name
    if summary is not None:
        skill.summary = summary
    if skill_id is not None:
        normalized = normalize_skill_id(skill_id)
        validate_skill_id(normalized)
        if normalized:
            existing = await skill_repo.get_by_skill_id(session, normalized)
            if existing is not None and existing.id != skill.id:
                raise SkillIdConflictError(f"Skill ID 已存在: {skill_id}")
        skill.skill_id = normalized
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
    await skill_repo.delete(session, skill)
