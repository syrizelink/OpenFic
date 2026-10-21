import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from app.agent_runtime.persistence.child_runs import (
    rollback_child_runs_for_parent_revisions,
)
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentRunMessage,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", [0, 5])
async def test_child_rollback_removes_only_affected_compactions(boundary: int):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AgentChildRun.__table__,
            AgentChildRunRequest.__table__,
            AgentRunMessage.__table__,
            AgentContextCompaction.__table__,
        ],
    )
    try:
        with Session(engine) as session:
            session.add(
                AgentChildRun(
                    id="child-run",
                    parent_session_id="parent",
                    parent_task_id="task",
                    parent_thread_id="parent",
                    child_thread_id="child",
                    agent_key="writer",
                    dispatch_id="dispatch",
                    tool_call_id="dispatch-call",
                )
            )
            request_boundaries = [0, 5] if boundary else [0]
            for request_seq, message_seq in enumerate(request_boundaries):
                session.add(
                    AgentChildRunRequest(
                        child_run_id="child-run",
                        parent_session_id="parent",
                        parent_task_id="task",
                        request_kind="dispatch" if request_seq == 0 else "notify",
                        content="request",
                        status="completed",
                        seq=request_seq,
                        parent_revision_id="revert"
                        if message_seq == boundary
                        else "keep",
                        child_user_message_id=f"message-{message_seq}",
                        child_user_message_seq=message_seq,
                    )
                )
            for seq in range(10):
                session.add(
                    AgentRunMessage(
                        id=f"message-{seq}",
                        session_id="child",
                        task_id="task",
                        project_id="project",
                        seq=seq,
                        role="assistant",
                        content="output",
                        status="complete",
                    )
                )
            for compaction_id, session_id, start_seq, end_seq in [
                ("before", "child", 1, 2),
                ("intersecting", "child", 3, 5),
                ("after", "child", 6, 8),
                ("unrelated", "other-child", 6, 8),
            ]:
                session.add(
                    AgentContextCompaction(
                        id=compaction_id,
                        session_id=session_id,
                        task_id="task",
                        project_id="project",
                        start_seq=start_seq,
                        end_seq=end_seq,
                        summary=compaction_id,
                        trigger="auto",
                    )
                )
            session.commit()

            # Exercise the real SQL against SQLite without a worker-thread driver.
            class RollbackSession:
                async def execute(self, statement):
                    return session.execute(statement)

                async def get(self, model, key):
                    return session.get(model, key)

                async def flush(self):
                    session.flush()

            await rollback_child_runs_for_parent_revisions(
                RollbackSession(), parent_revision_ids=["revert"]
            )
            session.commit()
            session.expire_all()

            remaining = session.execute(select(AgentContextCompaction)).scalars().all()
            assert {compaction.id for compaction in remaining} == (
                {"before", "unrelated"} if boundary else {"unrelated"}
            )
            messages = session.execute(select(AgentRunMessage)).scalars().all()
            assert {message.seq for message in messages} == set(range(boundary))
    finally:
        engine.dispose()
