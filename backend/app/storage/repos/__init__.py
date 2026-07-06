# -*- coding: utf-8 -*-
"""
Repository 模块 - 数据访问层。
"""

from app.storage.repos import (
    agent_definition_repo,
    agent_memory_repo,
    agent_rule_repo,
    character_repo,
    chapter_summary_repo,
    commit_repo,
    note_category_repo,
    note_repo,
    prompt_chain_version_repo,
    prompt_entry_repo,
    retrieval_index_repo,
    revision_repo,
    revision_chapter_snapshot_repo,
    revision_note_snapshot_repo,
    revision_world_entry_snapshot_repo,
    skill_repo,
    task_repo,
    task_message_repo,
    writing_activity_repo,
)

__all__ = [
    "agent_definition_repo",
    "agent_memory_repo",
    "agent_rule_repo",
    "character_repo",
    "chapter_summary_repo",
    "commit_repo",
    "note_category_repo",
    "note_repo",
    "prompt_chain_version_repo",
    "prompt_entry_repo",
    "retrieval_index_repo",
    "revision_repo",
    "revision_chapter_snapshot_repo",
    "revision_note_snapshot_repo",
    "revision_world_entry_snapshot_repo",
    "skill_repo",
    "task_message_repo",
    "task_repo",
    "writing_activity_repo",
]
