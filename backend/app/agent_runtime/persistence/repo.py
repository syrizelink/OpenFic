"""CRUD untuk persistensi pesan runtime Agent."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, func, or_, select
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
    """Mengubah baris ORM menjadi DTO eksternal dan mendeserialisasi field JSON."""
    return PersistedMessage(
        id=row.id,
        session_id=row.session_id,
        task_id=row.task_id,
        project_id=row.project_id,
        role=cast(Role, row.role),
        agent_id=row.agent_id,
        content=row.content,
        reasoning=row.reasoning,
        reasoning_duration_ms=row.reasoning_duration_ms,
        tool_calls=json.loads(row.tool_calls) if row.tool_calls else None,
        tool_call_id=row.tool_call_id,
        tool_name=row.tool_name,
        status=cast(Status, row.status),
        message_type=row.message_type or "message",
        display_channel=row.display_channel or "list",
        llm_visibility=row.llm_visibility or "visible",
        seq=row.seq,
        metadata=json.loads(row.message_metadata or "{}"),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def next_seq(session: AsyncSession, session_id: str) -> int:
    """Mengembalikan seq berikutnya yang tersedia untuk session tersebut; nilainya
    naik monoton di dalam session yang sama."""
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
    """Menulis satu pesan lalu commit; mengembalikan PersistedMessage (memuat seq
    yang dialokasikan)."""
    try:
        # Sebelum menulis, normalkan error jalur baca menjadi error tulis agar
        # PersistenceLoadError tidak merembes ke API tulis
        try:
            seq = await next_seq(session, session_id)
        except PersistenceLoadError as e:
            raise PersistenceWriteError(
                f"insert_message failed to allocate seq for session {session_id}"
            ) from e
        now = created_at or datetime.now(UTC)
        row = AgentRunMessage(
            id=message_id or generate_id(),
            session_id=session_id,
            task_id=task_id,
            project_id=project_id,
            role=role,
            agent_id=agent_id,
            content=content,
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
    """Mengembalikan semua pesan session tersebut, diurutkan naik berdasarkan
    seq."""
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


async def list_by_sessions(
    session: AsyncSession,
    session_ids: Sequence[str],
    *,
    roles: Sequence[str] | None = None,
    tool_names: Sequence[str] | None = None,
) -> dict[str, list[PersistedMessage]]:
    """Memuat pesan secara massal per session, lalu mengelompokkannya per session
    di memori."""
    normalized_ids = list(dict.fromkeys(session_id for session_id in session_ids if session_id))
    normalized_tool_names = list(
        dict.fromkeys(tool_name for tool_name in tool_names or () if tool_name)
    )
    if not normalized_ids:
        return {}
    try:
        query = select(AgentRunMessage).where(
            col(AgentRunMessage.session_id).in_(normalized_ids)
        )
        if roles and normalized_tool_names:
            query = query.where(
                or_(
                    col(AgentRunMessage.role).in_(roles),
                    col(AgentRunMessage.tool_name).in_(normalized_tool_names),
                )
            )
        elif roles:
            query = query.where(col(AgentRunMessage.role).in_(roles))
        elif normalized_tool_names:
            query = query.where(col(AgentRunMessage.tool_name).in_(normalized_tool_names))
        query = query.order_by(
            col(AgentRunMessage.session_id),
            col(AgentRunMessage.seq).asc(),
        )
        result = await session.execute(query)
        messages_by_session: dict[str, list[PersistedMessage]] = {}
        for row in result.scalars().all():
            messages_by_session.setdefault(row.session_id, []).append(_row_to_dto(row))
        return messages_by_session
    except SQLAlchemyError as e:
        raise PersistenceLoadError(
            f"list_by_sessions failed for {len(normalized_ids)} sessions"
        ) from e


async def delete_from_seq(
    session: AsyncSession, session_id: str, seq: int
) -> int:
    """Menghapus permanen semua baris dengan seq >= nilai yang ditentukan;
    mengembalikan jumlah baris yang dihapus. Dipakai untuk rollback revision
    bisnis."""
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
    """Menghapus semua baris user dengan status='pending' pada session tersebut;
    mengembalikan jumlah baris yang dihapus."""
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
    """Memperbarui status + updated_at pada satu pesan."""
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
    """Menghapus permanen satu baris berdasarkan id; mengembalikan apakah baris
    benar-benar dihapus. Dipakai lapisan API untuk rollback pending saat error."""
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
