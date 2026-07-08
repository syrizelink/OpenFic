# -*- coding: utf-8 -*-
"""Skill Router - Skill CRUD API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.skill import (
    SkillCreate,
    SkillImportResponse,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)
from app.api.schemas.skill_reference_doc import SkillReferenceDocResponse
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import skill_import_service, skill_service

router = APIRouter(tags=["skills"])


def _to_response(skill) -> SkillResponse:
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        summary=skill.summary,
        content=skill.content,
        is_enabled=skill.is_enabled,
        is_complete=skill_service.is_skill_complete(skill),
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _to_ref_response(doc) -> SkillReferenceDocResponse:
    return SkillReferenceDocResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        tokens=doc.tokens,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    data: SkillCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillResponse:
    try:
        logger.info(f"创建 Skill: name={data.name}")
        skill = await skill_service.create_skill(
            session,
            name=data.name,
            summary=data.summary,
            content=data.content,
            is_enabled=data.is_enabled,
        )
        return _to_response(skill)
    except skill_service.SkillValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SkillListResponse:
    result = await skill_service.list_skills(session, page=page, page_size=page_size)
    return SkillListResponse(
        items=[_to_response(skill) for skill in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post(
    "/skills/import",
    response_model=SkillImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_skill(
    files: Annotated[list[UploadFile], File()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillImportResponse:
    try:
        uploaded = [
            skill_import_service.UploadedFile(
                filename=f.filename or "",
                content=await f.read(),
            )
            for f in files
        ]
        logger.info(f"导入技能: 文件数={len(uploaded)}")
        result = await skill_import_service.import_skill(session, uploaded)
        return SkillImportResponse(
            skill=_to_response(result.skill),
            reference_docs=[_to_ref_response(d) for d in result.reference_docs],
            is_recognized=result.recognized,
        )
    except skill_import_service.SkillImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except skill_service.SkillValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/skills/{skill_db_id}", response_model=SkillResponse)
async def get_skill(
    skill_db_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillResponse:
    try:
        skill = await skill_service.get_skill(session, skill_db_id)
        return _to_response(skill)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/skills/{skill_db_id}", response_model=SkillResponse)
async def update_skill(
    skill_db_id: str,
    data: SkillUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillResponse:
    try:
        skill = await skill_service.update_skill(
            session,
            skill_db_id,
            name=data.name,
            summary=data.summary,
            content=data.content,
            is_enabled=data.is_enabled,
        )
        return _to_response(skill)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except skill_service.SkillValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/skills/{skill_db_id}/toggle", response_model=SkillResponse)
async def toggle_skill(
    skill_db_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillResponse:
    try:
        skill = await skill_service.toggle_skill(session, skill_db_id)
        return _to_response(skill)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except skill_service.SkillValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/skills/{skill_db_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_db_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await skill_service.delete_skill(session, skill_db_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
