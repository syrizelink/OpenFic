from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.repos import project_repo
from app.storage.services import skill_service


@dataclass(frozen=True)
class CommandCandidate:
    kind: Literal["skill"]
    id: str
    name: str
    description: str


async def search_commands(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    kind: Literal["skill"] = "skill",
    limit: int = 20,
) -> list[CommandCandidate]:
    if await project_repo.get_by_id(session, project_id) is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    if kind != "skill":
        return []

    skills = await skill_service.search_enabled_skills(session, query, limit=limit)
    return [
        CommandCandidate(
            kind="skill",
            id=skill.id,
            name=skill.name.strip(),
            description=skill.summary,
        )
        for skill in skills
    ]
