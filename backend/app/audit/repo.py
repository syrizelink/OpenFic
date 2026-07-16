"""Persistence queries for LLM audit logs."""

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.llm_audit_log import LLMAuditLog


@dataclass
class RevisionAggregation:
    revision_id: str
    llm_calls_count: int
    tokens_input_sum: int
    tokens_output_sum: int
    tokens_total_sum: int
    latency_ms_sum: int
    latency_ms_max: int
    latency_ms_avg: float
    tool_calls_total: int


@dataclass
class TaskAggregation:
    task_id: str
    llm_calls_total: int
    revisions_count: int
    tokens_input_total: int
    tokens_output_total: int
    tokens_grand_total: int
    duration_ms: int
    tool_calls_grand_total: int
    has_error: bool


class LLMAuditLogRepo:
    """Access layer for LLM audit records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, audit_log: LLMAuditLog) -> LLMAuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def get_by_id(self, audit_id: str) -> LLMAuditLog | None:
        result = await self.session.execute(select(LLMAuditLog).where(col(LLMAuditLog.id) == audit_id))
        return result.scalar_one_or_none()

    async def list_by_session(self, session_id: str) -> list[LLMAuditLog]:
        result = await self.session.execute(
            select(LLMAuditLog)
            .where(col(LLMAuditLog.session_id) == session_id)
            .order_by(col(LLMAuditLog.created_at), col(LLMAuditLog.call_sequence))
        )
        return list(result.scalars().all())

    async def list_by_task(self, task_id: str) -> list[LLMAuditLog]:
        result = await self.session.execute(
            select(LLMAuditLog)
            .where(col(LLMAuditLog.task_id) == task_id)
            .order_by(col(LLMAuditLog.created_at))
        )
        return list(result.scalars().all())

    async def list_by_revision(self, revision_id: str) -> list[LLMAuditLog]:
        result = await self.session.execute(
            select(LLMAuditLog)
            .where(col(LLMAuditLog.revision_id) == revision_id)
            .order_by(col(LLMAuditLog.call_sequence))
        )
        return list(result.scalars().all())

    async def update_revision_id(self, session_id: str, call_sequence: int, revision_id: str) -> None:
        result = await self.session.execute(
            select(LLMAuditLog)
            .where(col(LLMAuditLog.session_id) == session_id)
            .where(col(LLMAuditLog.call_sequence) == call_sequence)
        )
        audit_log = result.scalar_one_or_none()
        if audit_log:
            audit_log.revision_id = revision_id
            await self.session.flush()
            logger.debug(f"updated revision_id: {audit_log.id} -> {revision_id}")

    async def aggregate_by_revision(self, revision_id: str) -> RevisionAggregation | None:
        result = await self.session.execute(
            select(
                col(LLMAuditLog.revision_id),
                func.count(col(LLMAuditLog.id)).label("llm_calls_count"),
                func.sum(col(LLMAuditLog.tokens_input)).label("tokens_input_sum"),
                func.sum(col(LLMAuditLog.tokens_output)).label("tokens_output_sum"),
                func.sum(col(LLMAuditLog.tokens_total)).label("tokens_total_sum"),
                func.sum(col(LLMAuditLog.latency_ms)).label("latency_ms_sum"),
                func.max(col(LLMAuditLog.latency_ms)).label("latency_ms_max"),
                func.avg(col(LLMAuditLog.latency_ms)).label("latency_ms_avg"),
                func.sum(col(LLMAuditLog.tool_calls_count)).label("tool_calls_total"),
            )
            .where(col(LLMAuditLog.revision_id) == revision_id)
            .group_by(col(LLMAuditLog.revision_id))
        )
        row = result.fetchone()
        if row is None:
            return None
        return RevisionAggregation(
            revision_id=row.revision_id,
            llm_calls_count=row.llm_calls_count,
            tokens_input_sum=row.tokens_input_sum or 0,
            tokens_output_sum=row.tokens_output_sum or 0,
            tokens_total_sum=row.tokens_total_sum or 0,
            latency_ms_sum=row.latency_ms_sum or 0,
            latency_ms_max=row.latency_ms_max or 0,
            latency_ms_avg=row.latency_ms_avg or 0,
            tool_calls_total=row.tool_calls_total or 0,
        )

    async def aggregate_by_task(self, task_id: str) -> TaskAggregation | None:
        result = await self.session.execute(
            select(
                col(LLMAuditLog.task_id),
                func.count(col(LLMAuditLog.id)).label("llm_calls_total"),
                func.count(func.distinct(col(LLMAuditLog.revision_id))).label("revisions_count"),
                func.sum(col(LLMAuditLog.tokens_input)).label("tokens_input_total"),
                func.sum(col(LLMAuditLog.tokens_output)).label("tokens_output_total"),
                func.sum(col(LLMAuditLog.tokens_total)).label("tokens_grand_total"),
                func.sum(col(LLMAuditLog.latency_ms)).label("duration_ms"),
                func.sum(col(LLMAuditLog.tool_calls_count)).label("tool_calls_grand_total"),
                func.sum(case((col(LLMAuditLog.status) == "error", 1), else_=0)).label("error_count"),
            )
            .where(col(LLMAuditLog.task_id) == task_id)
            .group_by(col(LLMAuditLog.task_id))
        )
        row = result.fetchone()
        if row is None:
            return None
        return TaskAggregation(
            task_id=row.task_id,
            llm_calls_total=row.llm_calls_total,
            revisions_count=row.revisions_count,
            tokens_input_total=row.tokens_input_total or 0,
            tokens_output_total=row.tokens_output_total or 0,
            tokens_grand_total=row.tokens_grand_total or 0,
            duration_ms=row.duration_ms or 0,
            tool_calls_grand_total=row.tool_calls_grand_total or 0,
            has_error=(row.error_count or 0) > 0,
        )

    async def delete_by_session(self, session_id: str) -> int:
        result = await self.session.execute(select(LLMAuditLog).where(col(LLMAuditLog.session_id) == session_id))
        logs = result.scalars().all()
        for log in logs:
            await self.session.delete(log)
        await self.session.flush()
        return len(logs)
