# -*- coding: utf-8 -*-
"""ProjectRule Router - 项目规则 CRUD API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.api.schemas.project_rule import (
    ProjectRuleCreate,
    ProjectRuleListResponse,
    ProjectRuleReorder,
    ProjectRuleResponse,
    ProjectRuleUpdate,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import project_rule_service

router = APIRouter(tags=["project-rules"])


def _to_response(rule) -> ProjectRuleResponse:
    return ProjectRuleResponse(
        id=rule.id,
        project_id=rule.project_id,
        title=rule.title,
        content=rule.content,
        order_index=rule.order_index,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.post(
    "/projects/{project_id}/rules",
    response_model=ProjectRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    project_id: str,
    data: ProjectRuleCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectRuleResponse:
    await require_agent_settings_unlocked(session)
    logger.info(f"创建 ProjectRule: project_id={project_id}")
    try:
        rule = await project_rule_service.create_rule(
            session,
            project_id,
            title=data.title,
            content=data.content,
        )
        return _to_response(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/projects/{project_id}/rules", response_model=ProjectRuleListResponse)
async def list_rules(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ProjectRuleListResponse:
    try:
        result = await project_rule_service.list_rules(
            session, project_id, page=page, page_size=page_size
        )
        return ProjectRuleListResponse(
            items=[_to_response(rule) for rule in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/projects/{project_id}/rules/{rule_id}", response_model=ProjectRuleResponse)
async def get_rule(
    project_id: str,
    rule_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectRuleResponse:
    try:
        rule = await project_rule_service.get_rule(session, project_id, rule_id)
        return _to_response(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/projects/{project_id}/rules/{rule_id}", response_model=ProjectRuleResponse)
async def update_rule(
    project_id: str,
    rule_id: str,
    data: ProjectRuleUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectRuleResponse:
    await require_agent_settings_unlocked(session)
    try:
        rule = await project_rule_service.update_rule(
            session,
            project_id,
            rule_id,
            title=data.title,
            content=data.content,
        )
        return _to_response(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/projects/{project_id}/rules/reorder", response_model=list[ProjectRuleResponse])
async def reorder_rules(
    project_id: str,
    data: ProjectRuleReorder,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProjectRuleResponse]:
    await require_agent_settings_unlocked(session)
    try:
        rules = await project_rule_service.reorder_rules(session, project_id, data.rule_ids)
        return [_to_response(rule) for rule in rules]
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/projects/{project_id}/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_rule(
    project_id: str,
    rule_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await require_agent_settings_unlocked(session)
    try:
        await project_rule_service.delete_rule(session, project_id, rule_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
