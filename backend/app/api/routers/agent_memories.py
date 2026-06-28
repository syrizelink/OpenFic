# -*- coding: utf-8 -*-
"""AgentMemory Router - 记忆 CRUD API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.agent_memory import (
    AgentMemoryCreate,
    AgentMemoryListResponse,
    AgentMemoryReorder,
    AgentMemoryResponse,
    AgentMemoryUpdate,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import agent_memory_service

router = APIRouter(tags=["agent-memories"])


def _to_response(memory) -> AgentMemoryResponse:
    return AgentMemoryResponse(
        id=memory.id,
        content=memory.content,
        order_index=memory.order_index,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.post("/agent-memories", response_model=AgentMemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: AgentMemoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentMemoryResponse:
    logger.info("创建 AgentMemory")
    memory = await agent_memory_service.create_memory(session, content=data.content)
    return _to_response(memory)


@router.get("/agent-memories", response_model=AgentMemoryListResponse)
async def list_memories(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AgentMemoryListResponse:
    result = await agent_memory_service.list_memories(session, page=page, page_size=page_size)
    return AgentMemoryListResponse(
        items=[_to_response(memory) for memory in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/agent-memories/{memory_id}", response_model=AgentMemoryResponse)
async def get_memory(
    memory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentMemoryResponse:
    try:
        memory = await agent_memory_service.get_memory(session, memory_id)
        return _to_response(memory)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/agent-memories/{memory_id}", response_model=AgentMemoryResponse)
async def update_memory(
    memory_id: str,
    data: AgentMemoryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentMemoryResponse:
    try:
        memory = await agent_memory_service.update_memory(session, memory_id, content=data.content)
        return _to_response(memory)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/agent-memories/reorder", response_model=list[AgentMemoryResponse])
async def reorder_memories(
    data: AgentMemoryReorder,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AgentMemoryResponse]:
    memories = await agent_memory_service.reorder_memories(session, data.memory_ids)
    return [_to_response(memory) for memory in memories]


@router.delete("/agent-memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await agent_memory_service.delete_memory(session, memory_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
