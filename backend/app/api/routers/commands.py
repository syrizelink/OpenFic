from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.chapter import MentionCandidateItem
from app.api.schemas.command import (
    AgentComposerItemsResponse,
    CommandCandidateItem,
    CommandSearchResponse,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import agent_composer_service, command_service


router = APIRouter(tags=["commands"])


@router.get(
    "/projects/{project_id}/commands",
    response_model=CommandSearchResponse,
    summary="检索 Agent Command 候选项",
)
async def search_commands(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str, Query(description="Command 检索词")] = "",
    limit: Annotated[int, Query(ge=1, le=50, description="返回的最大候选数")] = 20,
    kind: Annotated[Literal["skill"], Query(description="Command 类型")] = "skill",
) -> CommandSearchResponse:
    try:
        items = await command_service.search_commands(
            session,
            project_id,
            query,
            kind=kind,
            limit=limit,
        )
        return CommandSearchResponse(
            items=[
                CommandCandidateItem(
                    kind=item.kind,
                    id=item.id,
                    name=item.name,
                    description=item.description,
                )
                for item in items
            ]
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/projects/{project_id}/agent-composer-items",
    response_model=AgentComposerItemsResponse,
    summary="获取 Agent 输入框菜单候选项",
)
async def list_agent_composer_items(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentComposerItemsResponse:
    try:
        items = await agent_composer_service.list_items(session, project_id)
        return AgentComposerItemsResponse(
            skills=[
                CommandCandidateItem(
                    kind=item.kind,
                    id=item.id,
                    name=item.name,
                    description=item.description,
                )
                for item in items.skills
            ],
            chapters=[
                MentionCandidateItem(
                    kind=item.kind,
                    id=item.id,
                    title=item.title,
                    label=item.label,
                    description=item.description,
                )
                for item in items.chapters
            ],
            notes=[
                MentionCandidateItem(
                    kind=item.kind,
                    id=item.id,
                    title=item.title,
                    label=item.label,
                    description=item.description,
                )
                for item in items.notes
            ],
            world_info_entries=[
                MentionCandidateItem(
                    kind=item.kind,
                    id=item.id,
                    title=item.title,
                    label=item.label,
                    description=item.description,
                )
                for item in items.world_info_entries
            ],
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
