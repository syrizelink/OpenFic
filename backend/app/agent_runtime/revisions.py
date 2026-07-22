"""Agent runtime business revisions and rollback helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import compaction_repo, repo as message_repo
from app.agent_runtime.persistence.child_runs import rollback_child_runs_for_parent_revisions
from app.agent_runtime.persistence.model import AgentRunMessage
from app.core.errors import NotFoundError
from app.storage.models.chapter import Chapter
from app.storage.models.character import Character
from app.storage.models.commit import Commit
from app.storage.models.note import Note
from app.storage.models.note import NoteCategory
from app.storage.models.revision import Revision
from app.storage.models.revision_character_snapshot import RevisionCharacterSnapshot
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.revision_note_snapshot import (
    RevisionNoteCategorySnapshot,
    RevisionNoteSnapshot,
)
from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot
from app.storage.models.world_info_entry import WorldInfoEntry
from app.storage.repos import (
    chapter_repo,
    character_repo,
    commit_repo,
    note_category_repo,
    note_repo,
    project_repo,
    revision_character_snapshot_repo,
    revision_chapter_snapshot_repo,
    revision_note_snapshot_repo,
    revision_repo,
    revision_world_entry_snapshot_repo,
    task_repo,
    volume_repo,
    world_info_entry_repo,
)
from app.storage.services import writing_activity_service
from app.storage.services.volume_service import refresh_volume_chapter_count
from app.storage.services.version_control_service import refresh_project_stats


@dataclass(frozen=True)
class ChapterImage:
    id: str
    project_id: str
    volume_id: str
    title: str
    content: str
    word_count: int
    order: int


@dataclass(frozen=True)
class NoteImage:
    id: str
    project_id: str
    category_id: str | None
    title: str
    content: str
    is_locked: bool
    is_hidden: bool


@dataclass(frozen=True)
class NoteCategoryImage:
    id: str
    project_id: str
    parent_id: str | None
    title: str


@dataclass(frozen=True)
class WorldEntryImage:
    id: str
    project_id: str
    world_info_id: str
    uid: int
    name: str
    order: int
    content: str
    token_count: int
    is_enabled: bool


@dataclass(frozen=True)
class CharacterImage:
    id: str
    project_id: str
    name: str
    description: str
    is_favorited: bool


@dataclass(frozen=True)
class AgentRollbackResult:
    rollback_revision: Revision
    affected_chapters: list[str]
    affected_notes: list[str]
    affected_note_categories: list[str]
    affected_world_entries: list[str]
    affected_characters: list[str]
    restored_message_content: str
    restored_checkpoint_id: str | None
    child_checkpoint_boundaries: list[tuple[str, str | None]]
    affected_child_run_ids: list[str]


def current_revision_id_from_state(state: dict) -> str | None:
    value = state.get("current_revision_id")
    return value if isinstance(value, str) and value else None


def _image_from_chapter(chapter: Chapter) -> ChapterImage:
    return ChapterImage(
        id=chapter.id,
        project_id=chapter.project_id,
        volume_id=chapter.volume_id,
        title=chapter.title,
        content=chapter.content,
        word_count=chapter.word_count,
        order=chapter.order,
    )


def _image_from_snapshot(snapshot: RevisionChapterSnapshot) -> ChapterImage | None:
    if not snapshot.exists:
        return None
    return ChapterImage(
        id=snapshot.chapter_id,
        project_id=snapshot.project_id,
        volume_id=getattr(snapshot, "volume_id", "") or "",
        title=snapshot.title or "",
        content=snapshot.content or "",
        word_count=snapshot.word_count or 0,
        order=snapshot.chapter_order or 1,
    )


def _snapshot_from_image(
    revision_id: str,
    project_id: str,
    chapter_id: str,
    image: ChapterImage | None,
) -> RevisionChapterSnapshot:
    if image is None:
        return RevisionChapterSnapshot(
            revision_id=revision_id,
            chapter_id=chapter_id,
            project_id=project_id,
            exists=False,
        )
    return RevisionChapterSnapshot(
        revision_id=revision_id,
        chapter_id=image.id,
        project_id=image.project_id,
        exists=True,
        title=image.title,
        content=image.content,
        word_count=image.word_count,
        chapter_order=image.order,
    )


def _has_changed(before: ChapterImage | None, after: ChapterImage | None) -> bool:
    if before is None or after is None:
        return before is not after
    return (
        before.title != after.title
        or before.content != after.content
        or before.word_count != after.word_count
        or before.order != after.order
        or before.volume_id != after.volume_id
    )


def _operation(before: ChapterImage | None, after: ChapterImage | None) -> str:
    if before is None:
        return "create"
    if after is None:
        return "delete"
    return "update"


def _commit_from_images(
    revision_id: str,
    chapter_id: str,
    before: ChapterImage | None,
    after: ChapterImage | None,
) -> Commit:
    return Commit(
        revision_id=revision_id,
        chapter_id=chapter_id,
        operation=_operation(before, after),
        snapshot_title=before.title if before else None,
        snapshot_content=before.content if before else None,
        snapshot_word_count=before.word_count if before else None,
        snapshot_order=before.order if before else None,
        new_title=after.title if after else None,
        new_content=after.content if after else None,
        new_word_count=after.word_count if after else None,
        new_order=after.order if after else None,
    )


def serialize_chapter(chapter: Chapter | ChapterImage) -> dict:
    created_at = getattr(chapter, "created_at", None)
    updated_at = getattr(chapter, "updated_at", None)
    return {
        "id": chapter.id,
        "project_id": chapter.project_id,
        "volume_id": chapter.volume_id,
        "title": chapter.title,
        "content": chapter.content,
        "word_count": chapter.word_count,
        "order": chapter.order,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
    }


async def begin_user_revision(
    session: AsyncSession,
    *,
    project_id: str,
    task_id: str,
    agent_session_id: str,
    user_message_id: str,
    user_message_seq: int,
    message: str,
    pre_run_checkpoint_id: str | None,
    graph_thread_id: str | None,
) -> Revision:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    revision = Revision(
        project_id=project_id,
        task_id=task_id,
        message=message,
        agent_session_id=agent_session_id,
        revision_type="agent",
        status="active",
        is_checkpoint=True,
        started_at=datetime.now(UTC),
        project_snapshot_title=project.title,
        project_snapshot_description=project.description,
        project_snapshot_word_count=project.word_count,
        project_snapshot_chapter_count=project.chapter_count,
        user_message_id=user_message_id,
        user_message_seq=user_message_seq,
        pre_run_checkpoint_id=pre_run_checkpoint_id,
        graph_thread_id=graph_thread_id,
    )
    revision = await revision_repo.create(session, revision)

    task = await task_repo.get_by_id(session, task_id)
    if task is not None:
        task.current_revision_id = revision.id
        task.current_message_id = user_message_id
        task.updated_at = datetime.now(UTC)
        await task_repo.update_task(session, task)

    user_message = await session.get(AgentRunMessage, user_message_id)
    if user_message is not None:
        metadata = json.loads(user_message.message_metadata or "{}")
        metadata["revision_id"] = revision.id
        user_message.message_metadata = json.dumps(metadata, ensure_ascii=False)
        user_message.updated_at = datetime.now(UTC)
        session.add(user_message)
        await session.flush()

    return revision


async def finalize_revision_status(
    session: AsyncSession,
    revision_id: str | None,
    status: str,
) -> None:
    if not revision_id:
        return
    await revision_repo.update_status(session, revision_id, status)


async def record_chapter_diffs(
    session: AsyncSession,
    *,
    revision_id: str,
    project_id: str,
    before: dict[str, ChapterImage],
    after: dict[str, ChapterImage],
) -> list[str]:
    existing_snapshots = await revision_chapter_snapshot_repo.list_by_revision(
        session, revision_id
    )
    snapshotted = {item.chapter_id for item in existing_snapshots}
    affected: list[str] = []
    def _chapter_order(chapter_id: str) -> int:
        image = after.get(chapter_id) or before.get(chapter_id)
        return image.order if image is not None else 0

    for chapter_id in sorted(set(before) | set(after), key=_chapter_order):
        old = before.get(chapter_id)
        new = after.get(chapter_id)
        if not _has_changed(old, new):
            continue
        affected.append(chapter_id)
        await commit_repo.create(session, _commit_from_images(revision_id, chapter_id, old, new))
        if chapter_id not in snapshotted:
            await revision_chapter_snapshot_repo.create(
                session,
                _snapshot_from_image(revision_id, project_id, chapter_id, old),
            )
            snapshotted.add(chapter_id)
    return affected


def images_by_id(chapters: list[Chapter]) -> dict[str, ChapterImage]:
    return {chapter.id: _image_from_chapter(chapter) for chapter in chapters}


def _image_from_note(note: Note) -> NoteImage:
    return NoteImage(
        id=note.id,
        project_id=note.project_id,
        category_id=note.category_id,
        title=note.title,
        content=note.content,
        is_locked=note.is_locked,
        is_hidden=note.is_hidden,
    )


def _image_from_note_snapshot(snapshot: RevisionNoteSnapshot) -> NoteImage | None:
    if not snapshot.exists:
        return None
    return NoteImage(
        id=snapshot.note_id,
        project_id=snapshot.project_id,
        category_id=snapshot.category_id,
        title=snapshot.title or "",
        content=snapshot.content or "",
        is_locked=snapshot.is_locked or False,
        is_hidden=snapshot.is_hidden or False,
    )


def _snapshot_from_note_image(
    revision_id: str,
    project_id: str,
    note_id: str,
    image: NoteImage | None,
) -> RevisionNoteSnapshot:
    if image is None:
        return RevisionNoteSnapshot(
            revision_id=revision_id,
            note_id=note_id,
            project_id=project_id,
            exists=False,
        )
    return RevisionNoteSnapshot(
        revision_id=revision_id,
        note_id=image.id,
        project_id=image.project_id,
        exists=True,
        category_id=image.category_id,
        title=image.title,
        content=image.content,
        is_locked=image.is_locked,
        is_hidden=image.is_hidden,
    )


def _note_has_changed(before: NoteImage | None, after: NoteImage | None) -> bool:
    if before is None or after is None:
        return before is not after
    return (
        before.title != after.title
        or before.content != after.content
        or before.category_id != after.category_id
        or before.is_locked != after.is_locked
        or before.is_hidden != after.is_hidden
    )


def note_images_by_id(notes: list[Note]) -> dict[str, NoteImage]:
    return {note.id: _image_from_note(note) for note in notes}


async def record_note_diffs(
    session: AsyncSession,
    *,
    revision_id: str,
    project_id: str,
    before: dict[str, NoteImage],
    after: dict[str, NoteImage],
) -> list[str]:
    existing_snapshots = await revision_note_snapshot_repo.list_by_revision(
        session, revision_id
    )
    snapshotted = {item.note_id for item in existing_snapshots}
    affected: list[str] = []
    for note_id in sorted(set(before) | set(after)):
        old = before.get(note_id)
        new = after.get(note_id)
        if not _note_has_changed(old, new):
            continue
        affected.append(note_id)
        if note_id not in snapshotted:
            await revision_note_snapshot_repo.create(
                session,
                _snapshot_from_note_image(revision_id, project_id, note_id, old),
            )
            snapshotted.add(note_id)
    return affected


def _image_from_note_category(category: NoteCategory) -> NoteCategoryImage:
    return NoteCategoryImage(
        id=category.id,
        project_id=category.project_id,
        parent_id=category.parent_id,
        title=category.title,
    )


def _image_from_note_category_snapshot(
    snapshot: RevisionNoteCategorySnapshot,
) -> NoteCategoryImage | None:
    if not snapshot.exists:
        return None
    return NoteCategoryImage(
        id=snapshot.category_id,
        project_id=snapshot.project_id,
        parent_id=snapshot.parent_id,
        title=snapshot.title or "",
    )


def _snapshot_from_note_category_image(
    revision_id: str,
    project_id: str,
    category_id: str,
    image: NoteCategoryImage | None,
) -> RevisionNoteCategorySnapshot:
    if image is None:
        return RevisionNoteCategorySnapshot(
            revision_id=revision_id,
            category_id=category_id,
            project_id=project_id,
            exists=False,
        )
    return RevisionNoteCategorySnapshot(
        revision_id=revision_id,
        category_id=image.id,
        project_id=image.project_id,
        exists=True,
        parent_id=image.parent_id,
        title=image.title,
    )


def _note_category_has_changed(
    before: NoteCategoryImage | None, after: NoteCategoryImage | None
) -> bool:
    if before is None or after is None:
        return before is not after
    return (
        before.title != after.title
        or before.parent_id != after.parent_id
    )


def note_category_images_by_id(
    categories: list[NoteCategory],
) -> dict[str, NoteCategoryImage]:
    return {cat.id: _image_from_note_category(cat) for cat in categories}


async def record_note_category_diffs(
    session: AsyncSession,
    *,
    revision_id: str,
    project_id: str,
    before: dict[str, NoteCategoryImage],
    after: dict[str, NoteCategoryImage],
) -> list[str]:
    existing_snapshots = (
        await revision_note_snapshot_repo.list_category_snapshots_by_revision(
            session, revision_id
        )
    )
    snapshotted = {item.category_id for item in existing_snapshots}
    affected: list[str] = []
    for category_id in sorted(set(before) | set(after)):
        old = before.get(category_id)
        new = after.get(category_id)
        if not _note_category_has_changed(old, new):
            continue
        affected.append(category_id)
        if category_id not in snapshotted:
            await revision_note_snapshot_repo.create_category_snapshot(
                session,
                _snapshot_from_note_category_image(
                    revision_id, project_id, category_id, old
                ),
            )
            snapshotted.add(category_id)
    return affected


def _image_from_world_entry(entry: WorldInfoEntry, project_id: str) -> WorldEntryImage:
    return WorldEntryImage(
        id=entry.id,
        project_id=project_id,
        world_info_id=entry.world_info_id,
        uid=entry.uid,
        name=entry.name,
        order=entry.order,
        content=entry.content,
        token_count=entry.token_count,
        is_enabled=entry.is_enabled,
    )


def _image_from_world_entry_snapshot(
    snapshot: RevisionWorldEntrySnapshot,
) -> WorldEntryImage | None:
    if not snapshot.exists:
        return None
    return WorldEntryImage(
        id=snapshot.entry_id,
        project_id=snapshot.project_id,
        world_info_id=snapshot.world_info_id or "",
        uid=snapshot.uid or 0,
        name=snapshot.name or "",
        order=snapshot.entry_order or 1,
        content=snapshot.content or "",
        token_count=snapshot.token_count or 0,
        is_enabled=snapshot.is_enabled if snapshot.is_enabled is not None else True,
    )


def _snapshot_from_world_entry_image(
    revision_id: str,
    project_id: str,
    entry_id: str,
    image: WorldEntryImage | None,
) -> RevisionWorldEntrySnapshot:
    if image is None:
        return RevisionWorldEntrySnapshot(
            revision_id=revision_id,
            entry_id=entry_id,
            project_id=project_id,
            exists=False,
        )
    return RevisionWorldEntrySnapshot(
        revision_id=revision_id,
        entry_id=image.id,
        project_id=image.project_id,
        exists=True,
        world_info_id=image.world_info_id,
        uid=image.uid,
        name=image.name,
        entry_order=image.order,
        content=image.content,
        token_count=image.token_count,
        is_enabled=image.is_enabled,
    )


def _world_entry_has_changed(
    before: WorldEntryImage | None,
    after: WorldEntryImage | None,
) -> bool:
    if before is None or after is None:
        return before is not after
    return (
        before.world_info_id != after.world_info_id
        or before.uid != after.uid
        or before.name != after.name
        or before.order != after.order
        or before.content != after.content
        or before.token_count != after.token_count
        or before.is_enabled != after.is_enabled
    )


def world_entry_images_by_id(
    entries: list[WorldInfoEntry],
    *,
    project_id: str,
) -> dict[str, WorldEntryImage]:
    return {entry.id: _image_from_world_entry(entry, project_id) for entry in entries}


async def record_world_entry_diffs(
    session: AsyncSession,
    *,
    revision_id: str,
    project_id: str,
    before: dict[str, WorldEntryImage],
    after: dict[str, WorldEntryImage],
) -> list[str]:
    existing_snapshots = await revision_world_entry_snapshot_repo.list_by_revision(
        session, revision_id
    )
    snapshotted = {item.entry_id for item in existing_snapshots}
    affected: list[str] = []
    for entry_id in sorted(set(before) | set(after)):
        old = before.get(entry_id)
        new = after.get(entry_id)
        if not _world_entry_has_changed(old, new):
            continue
        affected.append(entry_id)
        if entry_id not in snapshotted:
            await revision_world_entry_snapshot_repo.create(
                session,
                _snapshot_from_world_entry_image(revision_id, project_id, entry_id, old),
            )
            snapshotted.add(entry_id)
    return affected


def _image_from_character(character: Character) -> CharacterImage:
    return CharacterImage(
        id=character.id,
        project_id=character.project_id,
        name=character.name,
        description=character.description,
        is_favorited=character.is_favorited,
    )


def _image_from_character_snapshot(
    snapshot: RevisionCharacterSnapshot,
) -> CharacterImage | None:
    if not snapshot.exists:
        return None
    return CharacterImage(
        id=snapshot.character_id,
        project_id=snapshot.project_id,
        name=snapshot.name or "",
        description=snapshot.description or "",
        is_favorited=snapshot.is_favorited if snapshot.is_favorited is not None else False,
    )


def _snapshot_from_character_image(
    revision_id: str,
    project_id: str,
    character_id: str,
    image: CharacterImage | None,
) -> RevisionCharacterSnapshot:
    if image is None:
        return RevisionCharacterSnapshot(
            revision_id=revision_id,
            character_id=character_id,
            project_id=project_id,
            exists=False,
        )
    return RevisionCharacterSnapshot(
        revision_id=revision_id,
        character_id=image.id,
        project_id=image.project_id,
        exists=True,
        name=image.name,
        description=image.description,
        is_favorited=image.is_favorited,
    )


def _character_has_changed(
    before: CharacterImage | None,
    after: CharacterImage | None,
) -> bool:
    if before is None or after is None:
        return before is not after
    return (
        before.name != after.name
        or before.description != after.description
        or before.is_favorited != after.is_favorited
    )


def character_images_by_id(characters: list[Character]) -> dict[str, CharacterImage]:
    return {character.id: _image_from_character(character) for character in characters}


async def record_character_diffs(
    session: AsyncSession,
    *,
    revision_id: str,
    project_id: str,
    before: dict[str, CharacterImage],
    after: dict[str, CharacterImage],
) -> list[str]:
    existing_snapshots = await revision_character_snapshot_repo.list_by_revision(
        session, revision_id
    )
    snapshotted = {item.character_id for item in existing_snapshots}
    affected: list[str] = []
    for character_id in sorted(set(before) | set(after)):
        old = before.get(character_id)
        new = after.get(character_id)
        if not _character_has_changed(old, new):
            continue
        affected.append(character_id)
        if character_id not in snapshotted:
            await revision_character_snapshot_repo.create(
                session,
                _snapshot_from_character_image(revision_id, project_id, character_id, old),
            )
            snapshotted.add(character_id)
    return affected


def _sort_category_snapshots_by_hierarchy(
    snapshots: list[RevisionNoteCategorySnapshot],
) -> list[RevisionNoteCategorySnapshot]:
    """Sort category snapshots so parents precede children (topological order)."""
    by_id = {item.category_id: item for item in snapshots}
    visited: set[str] = set()
    result: list[RevisionNoteCategorySnapshot] = []

    def _visit(item: RevisionNoteCategorySnapshot) -> None:
        if item.category_id in visited:
            return
        if item.parent_id and item.parent_id in by_id:
            _visit(by_id[item.parent_id])
        visited.add(item.category_id)
        result.append(item)

    for item in snapshots:
        _visit(item)
    return result


async def _fallback_volume_id(session: AsyncSession, project_id: str) -> str:
    volumes = await volume_repo.list_by_project(session, project_id)
    if not volumes:
        raise NotFoundError(f"项目缺少卷，无法恢复章节: {project_id}")
    return volumes[0].id


async def _resolve_note_category_id(
    session: AsyncSession,
    project_id: str,
    category_id: str | None,
) -> str | None:
    if category_id is None:
        return None
    category = await note_category_repo.get_by_id(session, category_id)
    if category is None or category.project_id != project_id:
        return None
    return category.id


async def record_agent_activity_for_change(
    session: AsyncSession,
    *,
    revision_id: str,
    task_id: str,
    agent_session_id: str,
    before: ChapterImage | None,
    after: ChapterImage | None,
) -> None:
    if not _has_changed(before, after):
        return
    if before is None and after is not None:
        operation: Literal["create", "update", "delete", "move_to_volume"] = "create"
        chapter_id = after.id
        project_id = after.project_id
        title = after.title
    elif before is not None and after is None:
        operation = "delete"
        chapter_id = before.id
        project_id = before.project_id
        title = before.title
    elif before is not None and after is not None:
        operation = "move_to_volume" if before.volume_id != after.volume_id else "update"
        chapter_id = after.id
        project_id = after.project_id
        title = after.title
    else:
        return
    await writing_activity_service.record_activity(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        chapter_title=title,
        source="agent",
        operation=operation,
        old_word_count=before.word_count if before else 0,
        new_word_count=after.word_count if after else 0,
        revision_id=revision_id,
        task_id=task_id,
        agent_session_id=agent_session_id,
    )


async def rollback_revision_for_session(
    session: AsyncSession,
    *,
    agent_session_id: str,
    revision_id: str,
) -> AgentRollbackResult:
    target = await revision_repo.get_by_id(session, revision_id)
    if target is None:
        raise NotFoundError(f"版本不存在: {revision_id}")
    if target.agent_session_id != agent_session_id:
        raise NotFoundError(f"版本不属于会话: {revision_id}")
    if target.user_message_seq is None:
        raise ValueError("revision 缺少 user_message_seq，无法按用户消息回滚")

    revisions = await revision_repo.list_by_agent_session_from_seq(
        session,
        agent_session_id,
        target.user_message_seq,
    )
    restore_by_chapter: dict[str, RevisionChapterSnapshot] = {}
    restore_by_note: dict[str, RevisionNoteSnapshot] = {}
    restore_by_category: dict[str, RevisionNoteCategorySnapshot] = {}
    restore_by_world_entry: dict[str, RevisionWorldEntrySnapshot] = {}
    restore_by_character: dict[str, RevisionCharacterSnapshot] = {}
    for revision in revisions:
        snapshots = await revision_chapter_snapshot_repo.list_by_revision(
            session, revision.id
        )
        for snapshot in snapshots:
            restore_by_chapter.setdefault(snapshot.chapter_id, snapshot)
        note_snapshots = await revision_note_snapshot_repo.list_by_revision(
            session, revision.id
        )
        for note_snapshot in note_snapshots:
            restore_by_note.setdefault(note_snapshot.note_id, note_snapshot)
        category_snapshots = (
            await revision_note_snapshot_repo.list_category_snapshots_by_revision(
                session, revision.id
            )
        )
        for cat_snapshot in category_snapshots:
            restore_by_category.setdefault(cat_snapshot.category_id, cat_snapshot)
        world_entry_snapshots = await revision_world_entry_snapshot_repo.list_by_revision(
            session, revision.id
        )
        for world_entry_snapshot in world_entry_snapshots:
            restore_by_world_entry.setdefault(
                world_entry_snapshot.entry_id, world_entry_snapshot
            )
        character_snapshots = await revision_character_snapshot_repo.list_by_revision(
            session, revision.id
        )
        for character_snapshot in character_snapshots:
            restore_by_character.setdefault(
                character_snapshot.character_id, character_snapshot
            )

    restored_message_content = ""
    if target.user_message_id:
        user_message = await session.get(AgentRunMessage, target.user_message_id)
        if user_message is not None:
            restored_message_content = user_message.content
    if not restored_message_content and target.message.startswith("用户消息:"):
        restored_message_content = target.message.removeprefix("用户消息:").strip()

    rollback_revision = Revision(
        project_id=target.project_id,
        task_id=target.task_id,
        message=f"回滚到用户消息发送前: {restored_message_content or target.message}",
        agent_session_id=agent_session_id,
        revision_type="rollback",
        parent_revision_id=target.id,
        status="rollback",
        is_checkpoint=False,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        project_snapshot_title=target.project_snapshot_title,
        project_snapshot_description=target.project_snapshot_description,
        project_snapshot_word_count=target.project_snapshot_word_count,
        project_snapshot_chapter_count=target.project_snapshot_chapter_count,
        user_message_id=target.user_message_id,
        user_message_seq=target.user_message_seq,
        pre_run_checkpoint_id=target.pre_run_checkpoint_id,
        graph_thread_id=target.graph_thread_id,
    )
    rollback_revision = await revision_repo.create(session, rollback_revision)

    affected: list[str] = []
    affected_volume_ids: set[str] = set()
    deletes = [item for item in restore_by_chapter.values() if not item.exists]
    upserts = [item for item in restore_by_chapter.values() if item.exists]
    for snapshot in [*deletes, *upserts]:
        affected.append(snapshot.chapter_id)
        current = await chapter_repo.get_by_id(session, snapshot.chapter_id)
        before_image = _image_from_chapter(current) if current is not None else None
        after_image = _image_from_snapshot(snapshot)
        if before_image is not None:
            affected_volume_ids.add(before_image.volume_id)
        if after_image is not None:
            affected_volume_ids.add(after_image.volume_id)
        if after_image is None:
            if current is not None:
                await chapter_repo.delete(session, current)
        elif current is None:
            volume_id = after_image.volume_id or await _fallback_volume_id(
                session, after_image.project_id
            )
            await chapter_repo.create(
                session,
                Chapter(
                    id=after_image.id,
                    project_id=after_image.project_id,
                    volume_id=volume_id,
                    title=after_image.title,
                    content=after_image.content,
                    word_count=after_image.word_count,
                    order=after_image.order,
                ),
            )
        else:
            if after_image.volume_id:
                current.volume_id = after_image.volume_id
            current.title = after_image.title
            current.content = after_image.content
            current.word_count = after_image.word_count
            current.order = after_image.order
            current.updated_at = datetime.now(UTC)
            await chapter_repo.update_chapter(session, current)
        if _has_changed(before_image, after_image):
            await commit_repo.create(
                session,
                _commit_from_images(
                    rollback_revision.id,
                    snapshot.chapter_id,
                    before_image,
                    after_image,
                ),
            )
            await record_agent_activity_for_change(
                session,
                revision_id=rollback_revision.id,
                task_id=target.task_id or "",
                agent_session_id=agent_session_id,
                before=before_image,
                after=after_image,
            )

    for volume_id in affected_volume_ids:
        await refresh_volume_chapter_count(session, volume_id)

    affected_note_categories: list[str] = []
    cat_deletes = [item for item in restore_by_category.values() if not item.exists]
    cat_upserts = _sort_category_snapshots_by_hierarchy(
        [item for item in restore_by_category.values() if item.exists]
    )
    for cat_snapshot in [*cat_deletes, *cat_upserts]:
        affected_note_categories.append(cat_snapshot.category_id)
        current_cat = await note_category_repo.get_by_id(
            session, cat_snapshot.category_id
        )
        after_cat_image = _image_from_note_category_snapshot(cat_snapshot)
        if after_cat_image is None:
            if current_cat is not None:
                await note_category_repo.delete(session, current_cat)
        elif current_cat is None:
            await note_category_repo.create(
                session,
                NoteCategory(
                    id=after_cat_image.id,
                    project_id=after_cat_image.project_id,
                    parent_id=after_cat_image.parent_id,
                    title=after_cat_image.title,
                ),
            )
        else:
            current_cat.parent_id = after_cat_image.parent_id
            current_cat.title = after_cat_image.title
            current_cat.updated_at = datetime.now(UTC)
            await note_category_repo.update_category(session, current_cat)

    affected_notes: list[str] = []
    note_deletes = [item for item in restore_by_note.values() if not item.exists]
    note_upserts = [item for item in restore_by_note.values() if item.exists]
    for note_snapshot in [*note_deletes, *note_upserts]:
        affected_notes.append(note_snapshot.note_id)
        current_note = await note_repo.get_by_id(session, note_snapshot.note_id)
        after_note_image = _image_from_note_snapshot(note_snapshot)
        if after_note_image is None:
            if current_note is not None:
                await note_repo.delete(session, current_note)
        elif current_note is None:
            category_id = await _resolve_note_category_id(
                session, after_note_image.project_id, after_note_image.category_id
            )
            await note_repo.create(
                session,
                Note(
                    id=after_note_image.id,
                    project_id=after_note_image.project_id,
                    category_id=category_id,
                    title=after_note_image.title,
                    content=after_note_image.content,
                    is_locked=after_note_image.is_locked,
                    is_hidden=after_note_image.is_hidden,
                ),
            )
        else:
            category_id = await _resolve_note_category_id(
                session, after_note_image.project_id, after_note_image.category_id
            )
            current_note.category_id = category_id
            current_note.title = after_note_image.title
            current_note.content = after_note_image.content
            current_note.is_locked = after_note_image.is_locked
            current_note.is_hidden = after_note_image.is_hidden
            current_note.updated_at = datetime.now(UTC)
            await note_repo.update_note(session, current_note)

    affected_world_entries: list[str] = []
    world_entry_deletes = [
        item for item in restore_by_world_entry.values() if not item.exists
    ]
    world_entry_upserts = [
        item for item in restore_by_world_entry.values() if item.exists
    ]
    for entry_snapshot in [*world_entry_deletes, *world_entry_upserts]:
        affected_world_entries.append(entry_snapshot.entry_id)
        current_entry = await world_info_entry_repo.get_by_id(
            session, entry_snapshot.entry_id
        )
        after_entry_image = _image_from_world_entry_snapshot(entry_snapshot)
        if after_entry_image is None:
            if current_entry is not None:
                await world_info_entry_repo.delete(session, current_entry)
        elif current_entry is None:
            await world_info_entry_repo.create(
                session,
                WorldInfoEntry(
                    id=after_entry_image.id,
                    world_info_id=after_entry_image.world_info_id,
                    uid=after_entry_image.uid,
                    name=after_entry_image.name,
                    order=after_entry_image.order,
                    content=after_entry_image.content,
                    token_count=after_entry_image.token_count,
                    is_enabled=after_entry_image.is_enabled,
                ),
            )
        else:
            current_entry.world_info_id = after_entry_image.world_info_id
            current_entry.uid = after_entry_image.uid
            current_entry.name = after_entry_image.name
            current_entry.order = after_entry_image.order
            current_entry.content = after_entry_image.content
            current_entry.token_count = after_entry_image.token_count
            current_entry.is_enabled = after_entry_image.is_enabled
            current_entry.updated_at = datetime.now(UTC)
            await world_info_entry_repo.update_entry(session, current_entry)

    affected_characters: list[str] = []
    character_deletes = [item for item in restore_by_character.values() if not item.exists]
    character_upserts = [item for item in restore_by_character.values() if item.exists]
    for character_snapshot in [*character_deletes, *character_upserts]:
        affected_characters.append(character_snapshot.character_id)
        current_character = await character_repo.get_by_id(
            session, character_snapshot.character_id
        )
        after_character_image = _image_from_character_snapshot(character_snapshot)
        if after_character_image is None:
            if current_character is not None:
                await character_repo.delete(session, current_character)
        elif current_character is None:
            await character_repo.create(
                session,
                Character(
                    id=after_character_image.id,
                    project_id=after_character_image.project_id,
                    name=after_character_image.name,
                    description=after_character_image.description,
                    is_favorited=after_character_image.is_favorited,
                ),
            )
        else:
            current_character.name = after_character_image.name
            current_character.description = after_character_image.description
            current_character.is_favorited = after_character_image.is_favorited
            current_character.updated_at = datetime.now(UTC)
            await character_repo.update(session, current_character)

    await refresh_project_stats(session, target.project_id)
    await compaction_repo.delete_intersecting_or_after(
        session,
        agent_session_id,
        target.user_message_seq,
    )
    await message_repo.delete_from_seq(session, agent_session_id, target.user_message_seq)
    child_rollback_result = await rollback_child_runs_for_parent_revisions(
        session,
        parent_revision_ids=[revision.id for revision in revisions],
    )

    for revision in revisions:
        await revision_repo.update_status(session, revision.id, "rolled_back")

    previous = await revision_repo.latest_active_agent_revision_before_seq(
        session,
        agent_session_id,
        target.user_message_seq,
    )
    if target.task_id:
        task = await task_repo.get_by_id(session, target.task_id)
        if task is not None:
            task.current_revision_id = previous.id if previous else None
            task.current_message_id = previous.user_message_id if previous else None
            task.updated_at = datetime.now(UTC)
            await task_repo.update_task(session, task)

    return AgentRollbackResult(
        rollback_revision=rollback_revision,
        affected_chapters=list(dict.fromkeys(affected)),
        affected_notes=list(dict.fromkeys(affected_notes)),
        affected_note_categories=list(dict.fromkeys(affected_note_categories)),
        affected_world_entries=list(dict.fromkeys(affected_world_entries)),
        affected_characters=list(dict.fromkeys(affected_characters)),
        restored_message_content=restored_message_content,
        restored_checkpoint_id=target.pre_run_checkpoint_id,
        child_checkpoint_boundaries=child_rollback_result.checkpoint_boundaries,
        affected_child_run_ids=child_rollback_result.child_run_ids,
    )
