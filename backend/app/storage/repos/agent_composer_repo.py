"""Agent 输入框候选项的单次聚合查询。"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.skills import BUILTIN_SKILL_ID_PREFIX
from app.storage.models.chapter import Chapter
from app.storage.models.note import Note
from app.storage.models.project import Project
from app.storage.models.skill import Skill
from app.storage.models.volume import Volume
from app.storage.models.world_info import WorldInfo
from app.storage.models.world_info_entry import WorldInfoEntry


@dataclass(frozen=True)
class AgentComposerRow:
    kind: str
    id: str
    title: str
    label: str
    description: str | None
    updated_at: datetime | None
    skill_enabled: bool | None


def _project_marker(project_id: str):
    return select(
        literal("project", type_=String()).label("kind"),
        col(Project.id).label("id"),
        literal("", type_=String()).label("title"),
        literal("", type_=String()).label("label"),
        literal(None, type_=String()).label("description"),
        literal(None, type_=DateTime()).label("updated_at"),
        literal(None, type_=Boolean()).label("skill_enabled"),
    ).where(col(Project.id) == project_id)


def _candidate_rows(project_id: str):
    complete_skill_filter = (
        func.trim(col(Skill.name)) != "",
        func.trim(col(Skill.summary)) != "",
        func.trim(col(Skill.content)) != "",
    )
    custom_skills = select(
        literal("skill", type_=String()).label("kind"),
        col(Skill.id).label("id"),
        col(Skill.name).label("title"),
        col(Skill.name).label("label"),
        col(Skill.summary).label("description"),
        col(Skill.updated_at).label("updated_at"),
        col(Skill.is_enabled).label("skill_enabled"),
    ).where(
        col(Skill.id).not_like(f"{BUILTIN_SKILL_ID_PREFIX}%"),
        col(Skill.is_enabled) == True,  # noqa: E712
        *complete_skill_filter,
    )
    builtin_overrides = select(
        literal("skill_override", type_=String()).label("kind"),
        col(Skill.id).label("id"),
        literal("", type_=String()).label("title"),
        literal("", type_=String()).label("label"),
        literal(None, type_=String()).label("description"),
        col(Skill.updated_at).label("updated_at"),
        col(Skill.is_enabled).label("skill_enabled"),
    ).where(col(Skill.id).like(f"{BUILTIN_SKILL_ID_PREFIX}%"))
    chapters = (
        select(
            literal("chapter", type_=String()).label("kind"),
            col(Chapter.id).label("id"),
            col(Chapter.title).label("title"),
            col(Chapter.title).label("label"),
            col(Volume.title).label("description"),
            col(Chapter.updated_at).label("updated_at"),
            literal(None, type_=Boolean()).label("skill_enabled"),
        )
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
    )
    notes = select(
        literal("note", type_=String()).label("kind"),
        col(Note.id).label("id"),
        col(Note.title).label("title"),
        col(Note.title).label("label"),
        literal(None, type_=String()).label("description"),
        col(Note.updated_at).label("updated_at"),
        literal(None, type_=Boolean()).label("skill_enabled"),
    ).where(
        col(Note.project_id) == project_id,
        col(Note.is_hidden) == False,  # noqa: E712
    )
    world_info_entries = (
        select(
            literal("world_info_entry", type_=String()).label("kind"),
            col(WorldInfoEntry.id).label("id"),
            col(WorldInfoEntry.name).label("title"),
            col(WorldInfoEntry.name).label("label"),
            literal(None, type_=String()).label("description"),
            col(WorldInfoEntry.updated_at).label("updated_at"),
            literal(None, type_=Boolean()).label("skill_enabled"),
        )
        .join(WorldInfo, col(WorldInfoEntry.world_info_id) == col(WorldInfo.id))
        .where(col(WorldInfo.project_id) == project_id)
    )
    return union_all(
        _project_marker(project_id),
        custom_skills,
        builtin_overrides,
        chapters,
        notes,
        world_info_entries,
    ).subquery("agent_composer_candidates")


async def list_rows(
    session: AsyncSession,
    project_id: str,
    *,
    limit: int = 5,
) -> list[AgentComposerRow]:
    """单次数据库往返读取输入框候选项。"""
    result_limit = max(1, min(limit, 50))
    candidates = _candidate_rows(project_id)
    ranked_candidates = select(
        candidates,
        func.row_number()
        .over(
            partition_by=candidates.c.kind,
            order_by=(candidates.c.updated_at.desc(), candidates.c.id.asc()),
        )
        .label("candidate_rank"),
    ).subquery("ranked_agent_composer_candidates")
    result = await session.execute(
        select(ranked_candidates).where(
            (ranked_candidates.c.kind == "project")
            | (ranked_candidates.c.kind == "skill_override")
            | (ranked_candidates.c.candidate_rank <= result_limit)
        )
    )
    return [
        AgentComposerRow(
            kind=str(row.kind),
            id=str(row.id),
            title=str(row.title or ""),
            label=str(row.label or ""),
            description=str(row.description) if row.description is not None else None,
            updated_at=row.updated_at,
            skill_enabled=row.skill_enabled,
        )
        for row in result
    ]
