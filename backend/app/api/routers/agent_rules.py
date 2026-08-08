# -*- coding: utf-8 -*-
"""AgentRule Router - 规则 CRUD API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.agent_rule import (
    AgentRuleCreate,
    AgentRuleListResponse,
    AgentRuleReorder,
    AgentRuleResponse,
    AgentRuleScopeListResponse,
    AgentRuleScopeResponse,
    AgentRuleUpdate,
)
from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import agent_rule_service

router = APIRouter(tags=["agent-rules"])


def _to_response(rule) -> AgentRuleResponse:
    return AgentRuleResponse(
        id=rule.id,
        title=rule.title,
        content=rule.content,
        scope=rule.scope,
        project_id=rule.project_id,
        token_count=rule.token_count,
        order_index=rule.order_index,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.post("/agent-rules", response_model=AgentRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: AgentRuleCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRuleResponse:
    await require_agent_settings_unlocked(session)
    logger.info("创建 AgentRule")
    try:
        rule = await agent_rule_service.create_rule(
            session,
            title=data.title,
            content=data.content,
            scope=data.scope,
            project_id=data.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_response(rule)


@router.get("/agent-rules/scopes", response_model=AgentRuleScopeListResponse)
async def list_scopes(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRuleScopeListResponse:
    scopes = await agent_rule_service.list_scopes(session)
    return AgentRuleScopeListResponse(
        items=[
            AgentRuleScopeResponse(
                scope=s.scope,
                project_id=s.project_id,
                title=s.title,
                rule_count=s.rule_count,
            )
            for s in scopes
        ]
    )


@router.get("/agent-rules", response_model=AgentRuleListResponse)
async def list_rules(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    scope: Annotated[str, Query()] = "global",
    project_id: Annotated[str | None, Query()] = None,
) -> AgentRuleListResponse:
    result = await agent_rule_service.list_rules(
        session,
        page=page,
        page_size=page_size,
        scope=scope,
        project_id=project_id,
    )
    return AgentRuleListResponse(
        items=[_to_response(rule) for rule in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/agent-rules/{rule_id}", response_model=AgentRuleResponse)
async def get_rule(
    rule_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRuleResponse:
    try:
        rule = await agent_rule_service.get_rule(session, rule_id)
        return _to_response(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/agent-rules/{rule_id}", response_model=AgentRuleResponse)
async def update_rule(
    rule_id: str,
    data: AgentRuleUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRuleResponse:
    await require_agent_settings_unlocked(session)
    try:
        rule = await agent_rule_service.update_rule(
            session,
            rule_id,
            title=data.title,
            content=data.content,
        )
        return _to_response(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/agent-rules/reorder", response_model=list[AgentRuleResponse])
async def reorder_rules(
    data: AgentRuleReorder,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AgentRuleResponse]:
    await require_agent_settings_unlocked(session)
    rules = await agent_rule_service.reorder_rules(session, data.rule_ids)
    return [_to_response(rule) for rule in rules]


@router.delete("/agent-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await require_agent_settings_unlocked(session)
    try:
        await agent_rule_service.delete_rule(session, rule_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))