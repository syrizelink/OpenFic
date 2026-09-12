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
    summary="Mencari kandidat Agent Command",
)
async def search_commands(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str, Query(description="Kata pencarian Command")] = "",
    limit: Annotated[int, Query(ge=1, le=50, description="Jumlah maksimum kandidat yang dikembalikan")] = 20,
    kind: Annotated[Literal["skill"], Query(description="Tipe Command")] = "skill",
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
