from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.models.quick_prompt import QuickPrompt
from app.storage.services import quick_prompt_service

router = APIRouter(tags=["quick-prompts"])


class QuickPromptInput(BaseModel):
    command: str = Field(min_length=1, max_length=200)
    content: str = ""
    scope: Literal["global", "project"] = "global"
    project_id: str | None = None

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        value = value.strip()
        if not value or any(char.isspace() for char in value) or "/" in value:
            raise ValueError("指令不能包含空格或斜杠")
        return value


class QuickPromptResponse(QuickPromptInput):
    id: str


@router.get("/quick-prompts", response_model=list[QuickPromptResponse])
async def list_prompts(
    session: Annotated[AsyncSession, Depends(get_session)], project_id: str | None = None
) -> list[QuickPrompt]:
    return await quick_prompt_service.list_prompts(session, project_id)


@router.post("/quick-prompts", response_model=QuickPromptResponse, status_code=201)
async def create_prompt(
    data: QuickPromptInput, session: Annotated[AsyncSession, Depends(get_session)]
) -> QuickPrompt:
    await require_agent_settings_unlocked(session)
    try:
        return await quick_prompt_service.save_prompt(session, **data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/quick-prompts/{prompt_id}", response_model=QuickPromptResponse)
async def update_prompt(
    prompt_id: str, data: QuickPromptInput, session: Annotated[AsyncSession, Depends(get_session)]
) -> QuickPrompt:
    await require_agent_settings_unlocked(session)
    try:
        prompt = await quick_prompt_service.get_prompt(session, prompt_id)
        return await quick_prompt_service.save_prompt(session, prompt=prompt, **data.model_dump())
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/quick-prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(prompt_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    await require_agent_settings_unlocked(session)
    try:
        await quick_prompt_service.delete_prompt(session, prompt_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
