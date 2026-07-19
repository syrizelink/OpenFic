# -*- coding: utf-8 -*-
"""Skill Service - Skill 业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.skills import (
    BUILTIN_SKILL_ID_PREFIX,
    BuiltinSkill,
    load_builtin_skill,
    load_builtin_skills,
)
from app.storage.models.skill import Skill
from app.storage.repos import skill_reference_doc_repo, skill_repo


class SkillData(Protocol):
    """供 API、上下文与工具共享的 Skill 读取视图。"""

    id: str
    name: str
    summary: str
    content: str
    is_enabled: bool
    source: str
    created_at: datetime
    updated_at: datetime


class SkillReferenceData(Protocol):
    """供 API 与工具共享的参考文档读取视图。"""

    id: str
    title: str
    content: str
    tokens: int
    created_at: datetime
    updated_at: datetime


class SkillValidationError(Exception):
    """Skill 数据校验失败。"""


@dataclass
class SkillListResult:
    items: list[SkillData]
    total: int
    page: int
    page_size: int


def is_skill_complete(skill: SkillData) -> bool:
    return bool(skill.name.strip() and skill.summary.strip() and skill.content.strip())


def is_builtin_skill(skill: SkillData) -> bool:
    return skill.source == "builtin"


def _apply_builtin_enabled_overrides(
    skills: tuple[BuiltinSkill, ...],
    enabled_overrides: dict[str, Skill],
) -> list[BuiltinSkill]:
    return [
        BuiltinSkill(
            id=skill.id,
            name=skill.name,
            summary=skill.summary,
            content=skill.content,
            is_enabled=enabled_overrides.get(skill.id, skill).is_enabled,
            references=skill.references,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
        )
        for skill in skills
    ]


async def _load_builtin_skills_with_settings(
    session: AsyncSession,
    skill_ids: list[str] | None = None,
) -> list[BuiltinSkill]:
    skills = (
        load_builtin_skills()
        if skill_ids is None
        else tuple(
            skill
            for skill_id in dict.fromkeys(skill_ids)
            if (skill := load_builtin_skill(skill_id)) is not None
        )
    )
    settings = await skill_repo.list_by_ids(session, [skill.id for skill in skills])
    return _apply_builtin_enabled_overrides(
        skills,
        {setting.id: setting for setting in settings},
    )


async def _load_builtin_skill_with_setting(
    session: AsyncSession,
    skill_id: str,
) -> BuiltinSkill | None:
    skill = load_builtin_skill(skill_id)
    if skill is None:
        return None
    settings = await skill_repo.list_by_ids(session, [skill_id])
    return _apply_builtin_enabled_overrides(
        (skill,),
        {setting.id: setting for setting in settings},
    )[0]


async def _ensure_unique_name(session: AsyncSession, name: str) -> str:
    builtin_names = {skill.name for skill in load_builtin_skills()}
    existing_names = set(await skill_repo.get_all_names(session)) | builtin_names
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


async def get_skill(session: AsyncSession, skill_db_id: str) -> SkillData:
    builtin_skill = await _load_builtin_skill_with_setting(session, skill_db_id)
    if builtin_skill is not None:
        return builtin_skill
    skill = await skill_repo.get_by_id(session, skill_db_id)
    if skill is None:
        raise NotFoundError(f"Skill 不存在: {skill_db_id}")
    return skill


async def list_skills(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> SkillListResult:
    builtin_skills = await _load_builtin_skills_with_settings(session)
    builtin_count = len(builtin_skills)
    start = (page - 1) * page_size
    end = start + page_size
    builtin_page_items = builtin_skills[start:end]
    custom_offset = max(0, start - builtin_count)
    custom_limit = page_size - len(builtin_page_items)
    custom_total = await skill_repo.get_total(session)
    custom_skills = (
        await skill_repo.list_page(session, offset=custom_offset, limit=custom_limit)
        if custom_limit
        else []
    )
    items: list[SkillData] = [*builtin_page_items, *custom_skills]
    total = len(builtin_skills) + custom_total
    return SkillListResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_enabled_skills_by_ids(
    session: AsyncSession,
    ids: list[str],
) -> list[SkillData]:
    if not ids:
        return []
    builtin_skill_ids = [
        skill_id for skill_id in ids if skill_id.startswith(BUILTIN_SKILL_ID_PREFIX)
    ]
    builtin_skills = await _load_builtin_skills_with_settings(session, builtin_skill_ids)
    custom_skills = await skill_repo.list_by_ids(
        session,
        [skill_id for skill_id in ids if not skill_id.startswith(BUILTIN_SKILL_ID_PREFIX)],
    )
    skills: list[SkillData] = [*builtin_skills, *custom_skills]
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
    if is_builtin_skill(skill):
        raise SkillValidationError(f"不可编辑内置 Skill: {skill_db_id}")

    assert isinstance(skill, Skill)

    if name is not None and name != skill.name:
        if name in {builtin_skill.name for builtin_skill in load_builtin_skills()}:
            raise ConflictError(f"技能名称已存在: {name}")
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


async def list_reference_docs(
    session: AsyncSession,
    skill_db_id: str,
) -> Sequence[SkillReferenceData]:
    skill = await get_skill(session, skill_db_id)
    if isinstance(skill, BuiltinSkill):
        return list(skill.references)
    return await skill_reference_doc_repo.list_by_skill(session, skill_db_id)


async def toggle_skill(session: AsyncSession, skill_db_id: str) -> SkillData:
    skill = await get_skill(session, skill_db_id)
    if is_builtin_skill(skill):
        assert isinstance(skill, BuiltinSkill)
        override = await skill_repo.upsert(
            session,
            Skill(id=skill.id, is_enabled=not skill.is_enabled),
        )
        return _apply_builtin_enabled_overrides((skill,), {skill.id: override})[0]

    assert isinstance(skill, Skill)
    next_enabled = not skill.is_enabled
    if next_enabled and not is_skill_complete(skill):
        raise SkillValidationError("Skill 信息未完整填写，无法启用。")
    skill.is_enabled = next_enabled
    skill.updated_at = datetime.now(UTC)
    return await skill_repo.update(session, skill)


async def delete_skill(session: AsyncSession, skill_db_id: str) -> None:
    skill = await get_skill(session, skill_db_id)
    if is_builtin_skill(skill):
        raise SkillValidationError(f"不可删除内置 Skill: {skill_db_id}")

    assert isinstance(skill, Skill)
    await skill_reference_doc_repo.delete_by_skill(session, skill_db_id)
    await skill_repo.delete(session, skill)
