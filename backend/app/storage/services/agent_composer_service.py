"""Agent 输入框候选项服务。"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.skills import load_builtin_skills
from app.storage.repos import agent_composer_repo
from app.storage.services import mention_service, skill_service
from app.storage.services.command_service import CommandCandidate


@dataclass(frozen=True)
class AgentComposerItems:
    skills: list[CommandCandidate]
    chapters: list[mention_service.MentionCandidate]
    notes: list[mention_service.MentionCandidate]
    world_info_entries: list[mention_service.MentionCandidate]


def _display_title(value: str) -> str:
    return value.strip() or "未命名"


def _skill_sort_timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def list_items(
    session: AsyncSession,
    project_id: str,
    *,
    limit: int = 5,
) -> AgentComposerItems:
    """获取输入框菜单所需的各类最近候选项。"""
    rows = await agent_composer_repo.list_rows(session, project_id, limit=limit)
    if not any(row.kind == "project" for row in rows):
        raise NotFoundError(f"项目不存在: {project_id}")

    skill_overrides = {row.id: row for row in rows if row.kind == "skill_override"}
    skill_candidates: list[tuple[datetime, CommandCandidate]] = []
    for row in rows:
        if row.kind != "skill":
            continue
        skill_candidates.append(
            (
                _skill_sort_timestamp(row.updated_at),
                CommandCandidate(
                    kind="skill",
                    id=row.id,
                    name=_display_title(row.title),
                    description=row.description or "",
                ),
            )
        )

    for skill in load_builtin_skills():
        override = skill_overrides.get(skill.id)
        is_enabled = override.skill_enabled if override is not None else skill.is_enabled
        if not is_enabled or not skill_service.is_skill_complete(skill):
            continue
        skill_candidates.append(
            (
                _skill_sort_timestamp(override.updated_at if override else skill.updated_at),
                CommandCandidate(
                    kind="skill",
                    id=skill.id,
                    name=_display_title(skill.name),
                    description=skill.summary,
                ),
            )
        )

    skill_candidates.sort(key=lambda item: (item[0], item[1].name.lower(), item[1].id), reverse=True)

    chapters = [
        mention_service.MentionCandidate(
            kind="chapter",
            id=row.id,
            title=_display_title(row.title),
            label=_display_title(row.label),
            description=_display_title(row.description or ""),
        )
        for row in rows
        if row.kind == "chapter"
    ]
    notes = [
        mention_service.MentionCandidate(
            kind="note",
            id=row.id,
            title=_display_title(row.title),
            label=_display_title(row.label),
        )
        for row in rows
        if row.kind == "note"
    ]
    world_info_entries = [
        mention_service.MentionCandidate(
            kind="world_info_entry",
            id=row.id,
            title=_display_title(row.title),
            label=_display_title(row.label),
        )
        for row in rows
        if row.kind == "world_info_entry"
    ]

    return AgentComposerItems(
        skills=[item for _, item in skill_candidates[:limit]],
        chapters=chapters[:limit],
        notes=notes[:limit],
        world_info_entries=world_info_entries[:limit],
    )
