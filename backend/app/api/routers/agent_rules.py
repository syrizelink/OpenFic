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
    rule = await agent_rule_service.create_rule(
        session,
        title=data.title,
        content=data.content,
    )
    return _to_response(rule)


@router.get("/agent-rules", response_model=AgentRuleListResponse)
async def list_rules(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AgentRuleListResponse:
    result = await agent_rule_service.list_rules(session, page=page, page_size=page_size)
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
