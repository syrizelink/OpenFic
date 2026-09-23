"""Concurrency regression tests for agent edit tools."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _state() -> dict:
    return {
        "project_id": "proj-1",
        "session_id": "sess-1",
        "task_id": "task-1",
        "current_revision_id": "rev-1",
    }


class _LockState:
    def __init__(self) -> None:
        self.active = 0


class _TrackedLock:
    def __init__(self, state: _LockState) -> None:
        self._state = state

    async def __aenter__(self) -> None:
        self._state.active += 1

    async def __aexit__(self, *_args: object) -> None:
        self._state.active -= 1


async def _tracked_keyed_lock(
    state: _LockState,
    _key: object,
) -> _TrackedLock:
    return _TrackedLock(state)


def _tracked_keyed_lock_factory(state: _LockState):
    async def acquire(key: object) -> _TrackedLock:
        return await _tracked_keyed_lock(state, key)

    return acquire


def _assert_locked(state: _LockState) -> None:
    assert state.active >= 1


@pytest.mark.asyncio
async def test_edit_chapter_reads_and_writes_inside_lock() -> None:
    from app.agent_runtime.tools.impls.chapter.edit_chapter import EditChapterTool

    state = _LockState()
    session = AsyncMock()
    volume = SimpleNamespace(id="vol-1", title="第一卷", order=1)
    chapter = SimpleNamespace(
        id="chapter-1",
        project_id="proj-1",
        volume_id="vol-1",
        title="第一章",
        content="旧内容",
        word_count=3,
        order=1,
        updated_at=None,
    )

    async def get_chapter(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return chapter

    async def update_chapter(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return chapter

    tool = EditChapterTool(_state=_state())
    with (
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.create_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.keyed_lock",
            new=_tracked_keyed_lock_factory(state),
            create=True,
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.volume_repo.list_by_project",
            new=AsyncMock(return_value=[volume]),
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.chapter_repo.get_by_volume_ref",
            side_effect=get_chapter,
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.chapter_repo.update_chapter",
            side_effect=update_chapter,
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.record_chapter_diffs",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.record_agent_activity_for_change",
            new=AsyncMock(),
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.refresh_project_stats",
            new=AsyncMock(),
        ),
        patch(
            "app.retrieval.chapter_index.safe_maybe_enqueue_auto_index",
            new=AsyncMock(),
        ),
        patch(
            "app.retrieval.index_status.schedule_emit_index_status",
            new=lambda *_args, **_kwargs: None,
        ),
        patch("app.background.jobs.service.commit_and_notify", new=AsyncMock()),
    ):
        result = await tool._execute(
            volume_ref={"type": "order", "value": 1},
            chapter_ref={"type": "order", "value": 1},
            new_title="新标题",
        )

    assert json.loads(result)["success"] is True


@pytest.mark.asyncio
async def test_edit_volume_reads_and_writes_inside_lock() -> None:
    from app.agent_runtime.tools.impls.chapter.edit_volume import EditVolumeTool

    state = _LockState()
    session = AsyncMock()
    volume = SimpleNamespace(
        id="vol-1",
        project_id="proj-1",
        order=1,
        title="旧卷",
        description="旧描述",
        chapter_count=0,
        updated_at=None,
    )

    async def list_volumes(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return [volume]

    async def update_volume(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return volume

    tool = EditVolumeTool(_state=_state())
    with (
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_volume.create_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_volume.keyed_lock",
            new=_tracked_keyed_lock_factory(state),
            create=True,
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_volume.volume_repo.list_by_project",
            side_effect=list_volumes,
        ),
        patch(
            "app.agent_runtime.tools.impls.chapter.edit_volume.volume_repo.update_volume",
            side_effect=update_volume,
        ),
    ):
        result = await tool._execute(
            volume_ref={"type": "order", "value": 1},
            new_title="新卷",
        )

    assert json.loads(result)["success"] is True


@pytest.mark.asyncio
async def test_edit_note_reads_and_writes_inside_lock() -> None:
    from app.agent_runtime.tools.impls.note.edit_note import EditNoteTool

    state = _LockState()
    session = AsyncMock()
    note = SimpleNamespace(
        id="note-1",
        project_id="proj-1",
        category_id=None,
        title="笔记",
        content="旧内容",
        is_locked=False,
        is_hidden=False,
        updated_at=None,
    )

    async def get_note(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return note

    async def update_note(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return note

    tool = EditNoteTool(_state=_state())
    with (
        patch(
            "app.agent_runtime.tools.impls.note.edit_note.create_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note.keyed_lock",
            new=_tracked_keyed_lock_factory(state),
            create=True,
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note.note_repo.get_by_id",
            side_effect=get_note,
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note.note_repo.list_by_project",
            new=AsyncMock(return_value=[note]),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note.note_repo.update_note",
            side_effect=update_note,
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note.record_note_diffs",
            new=AsyncMock(),
        ),
        patch("app.background.jobs.service.commit_and_notify", new=AsyncMock()),
    ):
        result = await tool._execute(
            note_ref={"id": "note-1"},
            old_content="旧内容",
            new_content="新内容",
        )

    assert json.loads(result)["success"] is True


@pytest.mark.asyncio
async def test_edit_world_entry_reads_and_writes_inside_lock() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    state = _LockState()
    session = AsyncMock()
    world_info = SimpleNamespace(id="world-1")
    entry = SimpleNamespace(
        id="entry-1",
        world_info_id="world-1",
        uid=1,
        name="设定",
        order=1,
        content="旧内容",
        token_count=1,
        is_enabled=True,
    )

    async def get_world_info(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return world_info

    async def update_entry(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return entry

    tool = EditWorldEntryTool(_state=_state())
    with (
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.create_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.keyed_lock",
            new=_tracked_keyed_lock_factory(state),
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_repo.get_by_project_id",
            side_effect=get_world_info,
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo.list_all_by_world_info",
            new=AsyncMock(return_value=[entry]),
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_service.update_entry",
            side_effect=update_entry,
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.record_world_entry_diffs",
            new=AsyncMock(),
        ),
    ):
        result = await tool._execute(
            title="设定",
            old_content="旧内容",
            new_content="新内容",
        )

    assert json.loads(result)["success"] is True


@pytest.mark.asyncio
async def test_edit_note_category_resolves_target_inside_lock() -> None:
    from app.agent_runtime.tools.impls.note.edit_note_category import EditNoteCategoryTool

    state = _LockState()
    session = AsyncMock()
    category = SimpleNamespace(
        id="category-1",
        project_id="proj-1",
        parent_id=None,
        title="旧分类",
        updated_at=None,
    )

    async def get_category(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return category

    async def update_category(*_args: object, **_kwargs: object):
        _assert_locked(state)
        return category

    tool = EditNoteCategoryTool(_state=_state())
    with (
        patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.create_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.keyed_lock",
            new=_tracked_keyed_lock_factory(state),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.get_by_id",
            side_effect=get_category,
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.list_by_project",
            new=AsyncMock(return_value=[category]),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.update_category",
            side_effect=update_category,
        ),
        patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.record_note_category_diffs",
            new=AsyncMock(),
        ),
        patch("app.background.jobs.service.commit_and_notify", new=AsyncMock()),
    ):
        result = await tool._execute(
            category_ref={"id": "category-1"},
            new_title="新分类",
        )

    assert json.loads(result)["success"] is True
