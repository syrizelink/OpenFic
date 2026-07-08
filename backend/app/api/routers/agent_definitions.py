# -*- coding: utf-8 -*-
"""
Agent Definitions Router。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.agent_definition import (
    AgentDefinitionCreateRequest,
    AgentDefinitionListResponse,
    AgentDefinitionResponse,
    AgentToolCategoryListResponse,
    AgentToolCategoryResponse,
    AgentDefinitionUpdateRequest,
)
from app.agent_runtime.agents.definitions import agent_definition_from_record
from app.agent_runtime.agents.tool_categories import list_tool_categories
from app.core.errors import NotFoundError, ValidationError
from app.storage.database import get_session
from app.storage.services import agent_definition_service, prompt_chain_service

router = APIRouter(prefix="/agent-definitions", tags=["agent-definitions"])


def _to_response(defn) -> AgentDefinitionResponse:
    return AgentDefinitionResponse(
        key=defn.key,
        display_name=defn.display_name,
        description=defn.description,
        kind=defn.kind,
        prompt_agent_name=defn.prompt_agent_name,
        model_id=defn.model_id,
        enabled_tool_categories=list(defn.enabled_tool_categories),
        enabled_skills=list(defn.enabled_skills),
        metadata=dict(defn.metadata),
        enabled=defn.enabled,
        source=defn.source,
        delegatable_agents=list(defn.delegatable_agents),
    )


@router.get(
    "/tool-categories",
    response_model=AgentToolCategoryListResponse,
    summary="获取智能体工具分类",
)
async def list_definition_tool_categories() -> AgentToolCategoryListResponse:
    return AgentToolCategoryListResponse(
        categories=[
            AgentToolCategoryResponse(
                key=key,
                name=name,
                tool_keys=list(tool_keys),
            )
            for key, name, tool_keys in list_tool_categories()
        ]
    )


@router.get("", response_model=AgentDefinitionListResponse, summary="获取所有智能体定义")
async def list_definitions(
    session: AsyncSession = Depends(get_session),
) -> AgentDefinitionListResponse:
    defs = await agent_definition_service.list_definitions(session)
    return AgentDefinitionListResponse(
        definitions=[_to_response(d) for d in defs],
    )


@router.get(
    "/{key}",
    response_model=AgentDefinitionResponse,
    summary="获取单个智能体定义",
)
async def get_definition(
    key: str,
    session: AsyncSession = Depends(get_session),
) -> AgentDefinitionResponse:
    try:
        defn = await agent_definition_service.get_definition(session, key)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体定义不存在: {key}",
        )
    return _to_response(defn)


@router.post(
    "",
    response_model=AgentDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建自定义智能体",
)
async def create_definition(
    body: AgentDefinitionCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentDefinitionResponse:
    try:
        record = await agent_definition_service.create_definition(
            session,
            key=body.key,
            display_name=body.display_name,
            description=body.description,
            kind=body.kind,
            prompt_agent_name=body.prompt_agent_name,
            model_id=body.model_id,
            enabled_tool_categories=body.enabled_tool_categories,
            enabled_skills=body.enabled_skills,
            metadata=body.metadata,
            delegatable_agents=body.delegatable_agents,
        )
        await prompt_chain_service.create_initial_custom_agent_version(
            session,
            agent_name=body.key,
            kind=body.kind,
        )
        await session.commit()
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return _to_response(agent_definition_from_record(record))


@router.put(
    "/{key}",
    response_model=AgentDefinitionResponse,
    summary="更新智能体定义",
)
async def update_definition(
    key: str,
    body: AgentDefinitionUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentDefinitionResponse:
    try:
        record = await agent_definition_service.update_definition(
            session,
            key=key,
            display_name=body.display_name,
            description=body.description,
            kind=body.kind,
            prompt_agent_name=body.prompt_agent_name,
            model_id=body.model_id,
            enabled_tool_categories=body.enabled_tool_categories,
            enabled_skills=body.enabled_skills,
            metadata=body.metadata,
            enabled=body.enabled,
            delegatable_agents=body.delegatable_agents,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await session.commit()
    return _to_response(agent_definition_from_record(record))


@router.post(
    "/{key}/reset",
    response_model=AgentDefinitionResponse,
    summary="重置内置智能体为默认值",
)
async def reset_definition(
    key: str,
    session: AsyncSession = Depends(get_session),
) -> AgentDefinitionResponse:
    try:
        defn = await agent_definition_service.reset_definition(session, key)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await session.commit()
    return _to_response(defn)


@router.delete(
    "/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自定义智能体",
)
async def delete_definition(
    key: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        await agent_definition_service.delete_definition(session, key)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await session.commit()
