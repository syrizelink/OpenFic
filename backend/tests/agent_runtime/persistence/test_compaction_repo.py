import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import compaction_repo
from app.agent_runtime.persistence.errors import PersistenceWriteError


@pytest.mark.asyncio
async def test_insert_and_list_compactions(
    db_session: AsyncSession,
    sample_task,
) -> None:
    row = await compaction_repo.insert_compaction(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        start_seq=1,
        end_seq=3,
        summary="摘要",
        trigger="manual",
        source_input_tokens=3000,
        summary_tokens=120,
    )

    rows = await compaction_repo.list_by_session(db_session, "session_a")
    latest = await compaction_repo.latest_by_session(db_session, "session_a")

    assert row.id
    assert row.created_at is not None
    assert latest is not None
    assert latest.id == row.id
    assert [
        (
            item.start_seq,
            item.end_seq,
            item.summary,
            item.trigger,
            item.source_input_tokens,
            item.summary_tokens,
        )
        for item in rows
    ] == [(1, 3, "摘要", "manual", 3000, 120)]


@pytest.mark.asyncio
async def test_insert_rejects_overlapping_range(
    db_session: AsyncSession,
    sample_task,
) -> None:
    task_id = sample_task.id
    project_id = sample_task.project_id
    await compaction_repo.insert_compaction(
        db_session,
        session_id="session_a",
        task_id=task_id,
        project_id=project_id,
        start_seq=1,
        end_seq=3,
        summary="first",
        trigger="auto",
    )

    with pytest.raises(PersistenceWriteError, match="compaction_conflict"):
        await compaction_repo.insert_compaction(
            db_session,
            session_id="session_a",
            task_id=task_id,
            project_id=project_id,
            start_seq=3,
            end_seq=5,
            summary="overlap",
            trigger="manual",
        )

    await compaction_repo.insert_compaction(
        db_session,
        session_id="session_b",
        task_id=task_id,
        project_id=project_id,
        start_seq=3,
        end_seq=5,
        summary="other session",
        trigger="manual",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start_seq", "end_seq", "source_input_tokens", "summary_tokens"),
    [
        (-1, 3, 0, 0),
        (1, -3, 0, 0),
        (1, 3, -1, 0),
        (1, 3, 0, -1),
    ],
)
async def test_insert_rejects_negative_values(
    db_session: AsyncSession,
    sample_task,
    start_seq: int,
    end_seq: int,
    source_input_tokens: int,
    summary_tokens: int,
) -> None:
    with pytest.raises(PersistenceWriteError, match="invalid compaction"):
        await compaction_repo.insert_compaction(
            db_session,
            session_id="session_negative",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            start_seq=start_seq,
            end_seq=end_seq,
            summary="invalid",
            trigger="manual",
            source_input_tokens=source_input_tokens,
            summary_tokens=summary_tokens,
        )


@pytest.mark.asyncio
async def test_delete_intersecting_or_after_seq(
    db_session: AsyncSession,
    sample_task,
) -> None:
    for start_seq, end_seq in ((0, 2), (3, 4), (5, 7)):
        await compaction_repo.insert_compaction(
            db_session,
            session_id="session_a",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            start_seq=start_seq,
            end_seq=end_seq,
            summary=f"{start_seq}-{end_seq}",
            trigger="auto",
        )
    await compaction_repo.insert_compaction(
        db_session,
        session_id="session_b",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        start_seq=0,
        end_seq=9,
        summary="keep",
        trigger="auto",
    )

    deleted = await compaction_repo.delete_intersecting_or_after(
        db_session,
        "session_a",
        4,
    )

    assert deleted == 2
    rows = await compaction_repo.list_by_session(db_session, "session_a")
    assert [(row.start_seq, row.end_seq) for row in rows] == [(0, 2)]
    other_rows = await compaction_repo.list_by_session(db_session, "session_b")
    assert [(row.start_seq, row.end_seq) for row in other_rows] == [(0, 9)]


@pytest.mark.asyncio
async def test_copy_for_fork_skips_sparse_source_seq_map(
    db_session: AsyncSession,
    sample_task,
) -> None:
    await compaction_repo.insert_compaction(
        db_session,
        session_id="source_session",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        start_seq=1,
        end_seq=3,
        summary="skip sparse",
        trigger="manual",
    )

    copied = await compaction_repo.copy_for_fork(
        db_session,
        source_session_id="source_session",
        target_session_id="target_session",
        target_task_id=sample_task.id,
        project_id=sample_task.project_id,
        seq_map={1: 10, 3: 12},
    )

    assert copied == 0
    rows = await compaction_repo.list_by_session(db_session, "target_session")
    assert rows == []


@pytest.mark.asyncio
async def test_copy_for_fork_skips_non_contiguous_target_seq_map(
    db_session: AsyncSession,
    sample_task,
) -> None:
    await compaction_repo.insert_compaction(
        db_session,
        session_id="source_session",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        start_seq=1,
        end_seq=3,
        summary="skip non-contiguous",
        trigger="manual",
    )

    copied = await compaction_repo.copy_for_fork(
        db_session,
        source_session_id="source_session",
        target_session_id="target_session",
        target_task_id=sample_task.id,
        project_id=sample_task.project_id,
        seq_map={1: 10, 2: 12, 3: 13},
    )

    assert copied == 0
    rows = await compaction_repo.list_by_session(db_session, "target_session")
    assert rows == []


@pytest.mark.asyncio
async def test_copy_complete_ranges_for_fork(
    db_session: AsyncSession,
    sample_task,
) -> None:
    await compaction_repo.insert_compaction(
        db_session,
        session_id="source_session",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        start_seq=1,
        end_seq=3,
        summary="copy me",
        trigger="manual",
        source_input_tokens=100,
        summary_tokens=10,
    )
    await compaction_repo.insert_compaction(
        db_session,
        session_id="source_session",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        start_seq=4,
        end_seq=6,
        summary="skip me",
        trigger="auto",
    )

    copied = await compaction_repo.copy_for_fork(
        db_session,
        source_session_id="source_session",
        target_session_id="target_session",
        target_task_id=sample_task.id,
        project_id=sample_task.project_id,
        seq_map={1: 10, 2: 11, 3: 12, 4: 20, 5: 21},
    )

    assert copied == 1
    rows = await compaction_repo.list_by_session(db_session, "target_session")
    assert [
        (
            row.session_id,
            row.task_id,
            row.project_id,
            row.start_seq,
            row.end_seq,
            row.summary,
            row.trigger,
            row.source_input_tokens,
            row.summary_tokens,
        )
        for row in rows
    ] == [
        (
            "target_session",
            sample_task.id,
            sample_task.project_id,
            10,
            12,
            "copy me",
            "manual",
            100,
            10,
        )
    ]
