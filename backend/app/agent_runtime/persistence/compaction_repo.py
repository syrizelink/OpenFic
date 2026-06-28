"""Agent context compaction persistence CRUD."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.compaction_types import (
    CompactionTrigger,
    PersistedCompaction,
)
from app.agent_runtime.persistence.errors import (
    PersistenceLoadError,
    PersistenceWriteError,
)
from app.agent_runtime.persistence.model import AgentContextCompaction


def _validate_new_compaction(
    *,
    start_seq: int,
    end_seq: int,
    source_input_tokens: int,
    summary_tokens: int,
) -> None:
    if start_seq < 0:
        raise PersistenceWriteError(f"invalid compaction start_seq: {start_seq}")
    if end_seq < 0:
        raise PersistenceWriteError(f"invalid compaction end_seq: {end_seq}")
    if source_input_tokens < 0:
        raise PersistenceWriteError(
            f"invalid compaction source_input_tokens: {source_input_tokens}"
        )
    if summary_tokens < 0:
        raise PersistenceWriteError(
            f"invalid compaction summary_tokens: {summary_tokens}"
        )
    if start_seq > end_seq:
        raise PersistenceWriteError(
            f"invalid compaction range: start_seq={start_seq} end_seq={end_seq}"
        )


def _mapped_contiguous_range(
    *,
    start_seq: int,
    end_seq: int,
    seq_map: Mapping[int, int],
) -> tuple[int, int] | None:
    source_seq_values = range(start_seq, end_seq + 1)
    target_seq_values = [seq_map[source_seq] for source_seq in source_seq_values if source_seq in seq_map]
    if len(target_seq_values) != end_seq - start_seq + 1:
        return None
    if any(
        target_seq != target_seq_values[0] + offset
        for offset, target_seq in enumerate(target_seq_values)
    ):
        return None
    return target_seq_values[0], target_seq_values[-1]


def _row_to_dto(row: AgentContextCompaction) -> PersistedCompaction:
    return PersistedCompaction(
        id=row.id,
        session_id=row.session_id,
        task_id=row.task_id,
        project_id=row.project_id,
        start_seq=row.start_seq,
        end_seq=row.end_seq,
        summary=row.summary,
        trigger=row.trigger,  # type: ignore[arg-type]
        source_input_tokens=row.source_input_tokens,
        summary_tokens=row.summary_tokens,
        created_at=row.created_at,
    )


async def _ensure_non_overlapping(
    session: AsyncSession,
    *,
    session_id: str,
    start_seq: int,
    end_seq: int,
) -> None:
    result = await session.execute(
        select(AgentContextCompaction)
        .where(
            col(AgentContextCompaction.session_id) == session_id,
            col(AgentContextCompaction.start_seq) <= end_seq,
            col(AgentContextCompaction.end_seq) >= start_seq,
        )
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise PersistenceWriteError(
            "compaction_conflict: "
            f"session={session_id} range={start_seq}-{end_seq} "
            f"overlaps {existing.start_seq}-{existing.end_seq}"
        )


async def insert_compaction(
    session: AsyncSession,
    *,
    session_id: str,
    task_id: str,
    project_id: str,
    start_seq: int,
    end_seq: int,
    summary: str,
    trigger: CompactionTrigger,
    source_input_tokens: int = 0,
    summary_tokens: int = 0,
) -> PersistedCompaction:
    _validate_new_compaction(
        start_seq=start_seq,
        end_seq=end_seq,
        source_input_tokens=source_input_tokens,
        summary_tokens=summary_tokens,
    )

    try:
        await _ensure_non_overlapping(
            session,
            session_id=session_id,
            start_seq=start_seq,
            end_seq=end_seq,
        )
        row = AgentContextCompaction(
            session_id=session_id,
            task_id=task_id,
            project_id=project_id,
            start_seq=start_seq,
            end_seq=end_seq,
            summary=summary,
            trigger=trigger,
            source_input_tokens=source_input_tokens,
            summary_tokens=summary_tokens,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _row_to_dto(row)
    except PersistenceWriteError:
        await session.rollback()
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"insert_compaction failed for session {session_id} range={start_seq}-{end_seq}"
        ) from e


async def list_by_session(
    session: AsyncSession,
    session_id: str,
) -> list[PersistedCompaction]:
    try:
        result = await session.execute(
            select(AgentContextCompaction)
            .where(col(AgentContextCompaction.session_id) == session_id)
            .order_by(col(AgentContextCompaction.start_seq).asc())
        )
        return [_row_to_dto(row) for row in result.scalars().all()]
    except SQLAlchemyError as e:
        raise PersistenceLoadError(
            f"list_compactions_by_session failed for session {session_id}"
        ) from e


async def latest_by_session(
    session: AsyncSession,
    session_id: str,
) -> PersistedCompaction | None:
    try:
        result = await session.execute(
            select(AgentContextCompaction)
            .where(col(AgentContextCompaction.session_id) == session_id)
            .order_by(
                col(AgentContextCompaction.start_seq).desc(),
                col(AgentContextCompaction.created_at).desc(),
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return None if row is None else _row_to_dto(row)
    except SQLAlchemyError as e:
        raise PersistenceLoadError(
            f"latest_compaction_by_session failed for session {session_id}"
        ) from e


async def delete_intersecting_or_after(
    session: AsyncSession,
    session_id: str,
    seq: int,
) -> int:
    try:
        result = await session.execute(
            delete(AgentContextCompaction).where(
                col(AgentContextCompaction.session_id) == session_id,
                col(AgentContextCompaction.end_seq) >= seq,
            )
        )
        await session.flush()
        return getattr(result, "rowcount", 0) or 0
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"delete_compactions_intersecting_or_after failed for session {session_id} seq={seq}"
        ) from e


async def copy_for_fork(
    session: AsyncSession,
    *,
    source_session_id: str,
    target_session_id: str,
    target_task_id: str,
    project_id: str,
    seq_map: Mapping[int, int],
) -> int:
    try:
        result = await session.execute(
            select(AgentContextCompaction)
            .where(col(AgentContextCompaction.session_id) == source_session_id)
            .order_by(col(AgentContextCompaction.start_seq).asc())
        )
        copied = 0
        now = datetime.now(UTC)
        for source in result.scalars().all():
            mapped_range = _mapped_contiguous_range(
                start_seq=source.start_seq,
                end_seq=source.end_seq,
                seq_map=seq_map,
            )
            if mapped_range is None:
                continue
            start_seq, end_seq = mapped_range
            await _ensure_non_overlapping(
                session,
                session_id=target_session_id,
                start_seq=start_seq,
                end_seq=end_seq,
            )
            session.add(
                AgentContextCompaction(
                    session_id=target_session_id,
                    task_id=target_task_id,
                    project_id=project_id,
                    start_seq=start_seq,
                    end_seq=end_seq,
                    summary=source.summary,
                    trigger=source.trigger,
                    source_input_tokens=source.source_input_tokens,
                    summary_tokens=source.summary_tokens,
                    created_at=now,
                )
            )
            copied += 1
        await session.flush()
        return copied
    except PersistenceWriteError:
        await session.rollback()
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise PersistenceWriteError(
            f"copy_compactions_for_fork failed from {source_session_id} to {target_session_id}"
        ) from e
