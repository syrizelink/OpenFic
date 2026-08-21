from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.command import CommandCandidateItem, CommandSearchResponse
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import command_service


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
