"""Test helper to register SQLModel tables without importing app.storage.models."""

from __future__ import annotations


def register_sqlmodel_models() -> None:
    """Import table modules explicitly to populate SQLModel metadata for tests.

    Avoid importing ``app.storage.models`` directly in tests. That package import
    pulls in the full ``app.agent_runtime`` package via ``AgentRunMessage`` and
    makes simple in-memory DB setup much slower and less predictable.
    """

    from app.agent_runtime.persistence.model import AgentRunMessage
    from app.background.jobs.models import (
        BackgroundJob,
        BackgroundJobEvent,
        BackgroundJobItem,
    )
    from app.models.entities.model import Model
    from app.models.entities.model_provider import ModelProvider
    from app.storage.models.agent_audit_log import AgentAuditLog
    from app.storage.models.agent_memory import AgentMemory
    from app.storage.models.agent_rule import AgentRule
    from app.storage.models.character import Character
    from app.storage.models.chapter import Chapter
    from app.storage.models.chapter_summary import ChapterSummary
    from app.storage.models.commit import Commit
    from app.storage.models.project import Project
    from app.storage.models.prompt_chain_version import PromptChainVersion
    from app.storage.models.prompt_entry import PromptEntry
    from app.storage.models.retrieval_index import RetrievalIndex
    from app.storage.models.retrieval_chapter_index_state import (
        RetrievalChapterIndexState,
    )
    from app.storage.models.revision import Revision
    from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
    from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot
    from app.storage.models.setting import Setting
    from app.storage.models.skill import Skill
    from app.storage.models.task import Task
    from app.storage.models.task_message import TaskMessage
    from app.storage.models.volume import Volume
    from app.storage.models.note import Note, NoteCategory
    from app.storage.models.world_info import WorldInfo
    from app.storage.models.world_info_entry import WorldInfoEntry
    from app.storage.models.writing_activity_event import WritingActivityEvent

    _ = (
        AgentAuditLog,
        AgentMemory,
        AgentRule,
        AgentRunMessage,
        BackgroundJob,
        BackgroundJobEvent,
        BackgroundJobItem,
        Character,
        Chapter,
        ChapterSummary,
        Commit,
        Model,
        ModelProvider,
        Note,
        NoteCategory,
        Project,
        PromptChainVersion,
        PromptEntry,
        RetrievalIndex,
        RetrievalChapterIndexState,
        Revision,
        RevisionChapterSnapshot,
        RevisionWorldEntrySnapshot,
        Setting,
        Skill,
        Task,
        TaskMessage,
        Volume,
        WorldInfo,
        WorldInfoEntry,
        WritingActivityEvent,
    )
