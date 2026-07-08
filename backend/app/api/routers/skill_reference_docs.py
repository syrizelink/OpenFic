# -*- coding: utf-8 -*-
"""SkillReferenceDoc Router - 技能参考文档 CRUD API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.skill_reference_doc import (
    SkillReferenceDocCreate,
    SkillReferenceDocResponse,
    SkillReferenceDocUpdate,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import skill_reference_doc_service

router = APIRouter(tags=["skill-reference-docs"])


def _to_response(doc) -> SkillReferenceDocResponse:
    return SkillReferenceDocResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        tokens=doc.tokens,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post(
    "/skills/{skill_db_id}/reference-docs",
    response_model=SkillReferenceDocResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reference_doc(
    skill_db_id: str,
    data: SkillReferenceDocCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillReferenceDocResponse:
    try:
        logger.info(f"创建参考文档: skill_db_id={skill_db_id}")
        doc = await skill_reference_doc_service.create_reference_doc(
            session,
            skill_db_id,
            title=data.title,
            content=data.content,
        )
        return _to_response(doc)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/skills/{skill_db_id}/reference-docs",
    response_model=list[SkillReferenceDocResponse],
)
async def list_reference_docs(
    skill_db_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[SkillReferenceDocResponse]:
    try:
        docs = await skill_reference_doc_service.list_reference_docs(session, skill_db_id)
        return [_to_response(doc) for doc in docs]
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/skills/{skill_db_id}/reference-docs/{doc_id}",
    response_model=SkillReferenceDocResponse,
)
async def update_reference_doc(
    skill_db_id: str,
    doc_id: str,
    data: SkillReferenceDocUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillReferenceDocResponse:
    try:
        doc = await skill_reference_doc_service.update_reference_doc(
            session,
            skill_db_id,
            doc_id,
            title=data.title,
            content=data.content,
        )
        return _to_response(doc)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/skills/{skill_db_id}/reference-docs/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_reference_doc(
    skill_db_id: str,
    doc_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await skill_reference_doc_service.delete_reference_doc(session, skill_db_id, doc_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
