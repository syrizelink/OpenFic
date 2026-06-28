"""Agent 运行时消息持久化的 CRUD。"""

import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from app.agent_runtime.context.helpers import compile_canonical_mentions
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.errors import (
    PersistenceLoadError,
    PersistenceWriteError,
)
from app.agent_runtime.persistence.model import AgentRunMessage
from app.agent_runtime.persistence.types import (
    PersistedMessage,
    Role,
    Status,
)
from app.core.ids import generate_id


def _row_to_dto(row: AgentRunMessage) -> PersistedMessage:
    """将 ORM 行转换为外部 DTO，反序列化 JSON 字段。"""
    return PersistedMessage(
        id=row.id,
        session_id=row.session_id,
        task_id=row.task_id,
        project_id=row.project_id,
        role=row.role,  # type: ignore[arg-type]
        agent_id=row.agent_id,
        content=row.content,
        reasoning=row.reasoning,
        reasoning_duration_ms=row.reasoning_duration_ms,
        tool_calls=json.loads(row.tool_calls) if row.tool_calls else None,
        tool_call_id=row.tool_call_id,
        tool_name=row.tool_name,
        status=row.status,  # type: ignore[arg-type]
        message_type=row.message_type or "message",
        display_channel=row.display_channel or "list",
        llm_visibility=row.llm_visibility or "visible",
        seq=row.seq,
        metadata=json.loads(row.message_metadata or "{}"),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def next_seq(session: AsyncSession, session_id: str) -> int:
    """返回该 session 下一个可用 seq；同一 session 内单调递增。"""
    try:
        result = await session.execute(
            select(func.max(col(AgentRunMessage.seq))).where(
                col(AgentRunMessage.session_id) == session_id
            )
        )
        current = result.scalar_one_or_none()
        return 0 if current is None else current + 1
    except SQLAlchemyError as e:
        raise PersistenceLoadError(
            f"next_seq failed for session {session_id}"
        ) from e


async def insert_message(
    session: AsyncSession,
    *,
    session_id: str,
    task_id: str,
    project_id: str,
    role: Role,
    status: Status,
    content: str = "",
    reasoning: str | None = None,
    reasoning_duration_ms: int | None = None,
    tool_calls: list[dict] | None = None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
    agent_id: str | None = None,
    message_type: str = "message",
    display_channel: str = "list",
    llm_visibility: str = "visible",
    metadata: dict | None = None,
    message_id: str | None = None,
    created_at: datetime | None = None,
) -> PersistedMessage:
    """写入一条消息并 commit；返回 PersistedMessage（含分配的 seq）。"""
    try:
        # 在写入前先把读路径的错误归一化为写错误，避免 PersistenceLoadError 泄露到写 API
        try:
            seq = await next_seq(session, session_id)
        except PersistenceLoadError as e:
            raise PersistenceWriteError(
                f"insert_message failed to allocate seq for session {session_id}"
            ) from e
        normalized_content = content
        if role == "user" and isinstance(content, str) and "<of-mention" in content:
            normalized_content = await compile_canonical_mentions(content, session)
        now = created_at or datetime.now(UTC)
        row = AgentRunMessage(
            id=message_id or generate_id(),
            session_id=session_id,
            task_id=task_id,
            project_id=project_id,
            role=role,
            agent_id=agent_id,
            content=normalized_content,
            reasoning=reasoning,
            reasoning_duration_ms=reasoning_duration_ms,
            tool_calls=json.dumps(tool_calls) if tool_calls is not None else None,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            message_type=message_type,
            display_channel=display_channel,
            llm_visibility=llm_visibility,
            seq=seq,
            message_metadata=json.dumps(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _row_to_dto(row)
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"insert_message failed for session {session_id} role={role}"
        ) from e


async def list_by_session(
    session: AsyncSession, session_id: str
) -> list[PersistedMessage]:
    """按 seq 升序返回该 session 的全部消息。"""
    try:
        result = await session.execute(
            select(AgentRunMessage)
            .where(col(AgentRunMessage.session_id) == session_id)
            .order_by(col(AgentRunMessage.seq).asc())
        )
        rows = result.scalars().all()
        return [_row_to_dto(r) for r in rows]
    except SQLAlchemyError as e:
        raise PersistenceLoadError(
            f"list_by_session failed for session {session_id}"
        ) from e


async def delete_from_seq(
    session: AsyncSession, session_id: str, seq: int
) -> int:
    """硬删 seq >= 指定值的所有行；返回删除条数。用于业务 revision rollback。"""
    try:
        result = await session.execute(
            delete(AgentRunMessage).where(
                col(AgentRunMessage.session_id) == session_id,
                col(AgentRunMessage.seq) >= seq,
            )
        )
        await session.flush()
        return getattr(result, "rowcount", 0) or 0
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"delete_from_seq failed for session {session_id} seq>={seq}"
        ) from e


async def delete_pending_by_session(
    session: AsyncSession, session_id: str
) -> int:
    """删除该 session 所有 status='pending' 的 user 行；返回删除条数。"""
    try:
        result = await session.execute(
            delete(AgentRunMessage).where(
                col(AgentRunMessage.session_id) == session_id,
                col(AgentRunMessage.role) == "user",
                col(AgentRunMessage.status) == "pending",
            )
        )
        await session.commit()
        return getattr(result, "rowcount", 0) or 0
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"delete_pending_by_session failed for session {session_id}"
        ) from e


async def update_status(
    session: AsyncSession, message_id: str, status: Status
) -> None:
    """更新单条消息的 status + updated_at。"""
    try:
        row = await session.get(AgentRunMessage, message_id)
        if row is None:
            raise PersistenceWriteError(
                f"update_status: message {message_id} not found"
            )
        row.status = status
        row.updated_at = datetime.now(UTC)
        session.add(row)
        await session.commit()
    except PersistenceWriteError:
        await session.rollback()
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"update_status failed for message {message_id}"
        ) from e


async def update_latest_tool_message_content(
    session: AsyncSession,
    *,
    session_id: str,
    tool_call_id: str,
    content: str,
) -> None:
    try:
        result = await session.execute(
            select(AgentRunMessage)
            .where(
                col(AgentRunMessage.session_id) == session_id,
                col(AgentRunMessage.role) == "tool",
                col(AgentRunMessage.tool_call_id) == tool_call_id,
            )
            .order_by(col(AgentRunMessage.seq).desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise PersistenceWriteError(
                f"update_latest_tool_message_content: tool message not found for {tool_call_id}"
            )
        row.content = content
        row.updated_at = datetime.now(UTC)
        session.add(row)
        await session.commit()
    except PersistenceWriteError:
        await session.rollback()
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"update_latest_tool_message_content failed for tool_call_id {tool_call_id}"
        ) from e


async def delete_by_id(session: AsyncSession, message_id: str) -> bool:
    """按 id 硬删一条；返回是否实际删除。API 层异常回滚 pending 用。"""
    try:
        result = await session.execute(
            delete(AgentRunMessage).where(col(AgentRunMessage.id) == message_id)
        )
        await session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"delete_by_id failed for message {message_id}"
        ) from e
