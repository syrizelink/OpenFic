"""Project persisted parent and subagent writes into session change data."""

from __future__ import annotations

import json
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from typing import Any, Literal, Sequence, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.child_runs import (
    get_child_run_agent_number,
    list_child_runs_for_parents,
)
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
)
from app.storage.models.revision import Revision


ChangeKind = Literal["chapter", "note", "world_entry", "character"]
ChangeLineType = Literal["context", "added", "removed"]
ChangeSectionType = Literal["content", "title"]


@dataclass
class AgentChangeLine:
    type: ChangeLineType
    before_line_number: int | None
    after_line_number: int | None
    text: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "before_line_number": self.before_line_number,
            "after_line_number": self.after_line_number,
            "text": self.text,
        }


@dataclass
class AgentChangeSection:
    type: ChangeSectionType
    lines: list[AgentChangeLine]

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "lines": [line.to_payload() for line in self.lines],
        }


@dataclass
class AgentChangeItem:
    key: str
    kind: ChangeKind
    title: str
    operation: str
    sections: list[AgentChangeSection]
    source_message_id: str
    source: Literal["primary", "subagent", "session"]
    title_before: str | None = None
    title_after: str | None = None
    path: list[str] = field(default_factory=list)
    child_run_id: str | None = None
    request_id: str | None = None
    agent_key: str | None = None
    agent_number: str | None = None
    revision_id: str | None = None
    added: int = 0
    removed: int = 0
    _content_before: list[str] | None = field(default=None, repr=False)
    _content_after: list[str] | None = field(default=None, repr=False)

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "title": self.title,
            "title_before": self.title_before,
            "title_after": self.title_after,
            "operation": self.operation,
            "sections": [section.to_payload() for section in self.sections],
            "added": self.added,
            "removed": self.removed,
            "source_message_id": self.source_message_id,
            "source": self.source,
            "path": self.path,
            "child_run_id": self.child_run_id,
            "request_id": self.request_id,
            "agent_key": self.agent_key,
            "agent_number": self.agent_number,
            "revision_id": self.revision_id,
        }


@dataclass
class AgentChangeSummary:
    items: list[AgentChangeItem]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def added(self) -> int:
        return sum(item.added for item in self.items)

    @property
    def removed(self) -> int:
        return sum(item.removed for item in self.items)

    def to_payload(self) -> dict[str, Any]:
        return {
            "item_count": self.item_count,
            "added": self.added,
            "removed": self.removed,
            "items": [item.to_payload() for item in self.items],
        }


@dataclass
class AgentSubagentRunChanges:
    child_run_id: str
    child_thread_id: str
    request_id: str | None
    child_user_message_id: str | None
    agent_key: str
    agent_number: str | None
    changes: AgentChangeSummary

    def to_payload(self) -> dict[str, Any]:
        return {
            "child_run_id": self.child_run_id,
            "child_thread_id": self.child_thread_id,
            "request_id": self.request_id,
            "child_user_message_id": self.child_user_message_id,
            "agent_key": self.agent_key,
            "agent_number": self.agent_number,
            "changes": self.changes.to_payload(),
        }


@dataclass
class AgentTurnChanges:
    revision_id: str
    user_message_id: str | None
    user_message_seq: int | None
    changes: AgentChangeSummary
    subagent_runs: list[AgentSubagentRunChanges]

    def to_payload(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "user_message_id": self.user_message_id,
            "user_message_seq": self.user_message_seq,
            "changes": self.changes.to_payload(),
            "subagent_runs": [run.to_payload() for run in self.subagent_runs],
        }


@dataclass
class AgentSessionChanges:
    session_id: str
    turns: list[AgentTurnChanges]
    session_changes: AgentChangeSummary

    def to_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turns": [turn.to_payload() for turn in self.turns],
            "session_changes": self.session_changes.to_payload(),
        }


@dataclass(frozen=True)
class _ChangeCandidate:
    row: object
    definition: _ChangeDefinition
    raw_diff: dict[str, Any]
    revision_id: str | None
    child_run: AgentChildRun | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class _ChangeDefinition:
    kind: ChangeKind
    metadata_key: str
    id_field: str
    title_fields: tuple[str, ...]


_CHANGE_DEFINITIONS: tuple[_ChangeDefinition, ...] = (
    _ChangeDefinition("chapter", "chapter_diff", "chapter_id", ("chapter_title", "title")),
    _ChangeDefinition("note", "note_diff", "note_id", ("note_title", "title")),
    _ChangeDefinition(
        "world_entry",
        "world_entry_diff",
        "entry_id",
        ("entry_title", "title", "name"),
    ),
    _ChangeDefinition(
        "character",
        "character_diff",
        "character_id",
        ("character_name", "title", "name"),
    ),
)

_IGNORED_RESULT_REASONS = {"approval_preview", "ask_user_pending", "cancelled"}
_CHANGE_TOOL_NAMES = (
    "write_chapter",
    "edit_chapter",
    "delete_chapter",
    "move_chapter_to_volume",
    "write_note",
    "edit_note",
    "delete_note",
    "move_note",
    "create_world_entry",
    "edit_world_entry",
    "delete_world_entry",
    "create_character",
    "edit_character",
    "delete_character",
)


def _as_record(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _parse_content(value: object) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _row_metadata(row: object) -> dict[str, Any]:
    metadata = getattr(row, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    raw_metadata = getattr(row, "message_metadata", None)
    if not isinstance(raw_metadata, str):
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _result_is_executed(row: object, result: dict[str, Any]) -> bool:
    if getattr(row, "status", None) in {"aborted", "error"}:
        return False
    containers = [result]
    data = _as_record(result.get("data"))
    if data is not None:
        containers.append(data)
    for container in containers:
        if container.get("success") is False:
            return False
        if container.get("type") == "preview":
            return False
        if container.get("reason") in _IGNORED_RESULT_REASONS:
            return False
        if container.get("error"):
            return False
    return True


def _result_metadata(result: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    containers = [result]
    data = _as_record(result.get("data"))
    if data is not None:
        containers.append(data)
    for container in containers:
        raw_metadata = _as_record(container.get("metadata"))
        if raw_metadata is not None:
            metadata.update(raw_metadata)
        for definition in _CHANGE_DEFINITIONS:
            raw_diff = _as_record(container.get(definition.metadata_key))
            if raw_diff is not None:
                metadata[definition.metadata_key] = raw_diff
    return metadata


def _extract_candidates(
    row: object,
    *,
    revision_id: str | None,
    child_run: AgentChildRun | None = None,
    request_id: str | None = None,
) -> list[_ChangeCandidate]:
    if getattr(row, "role", None) != "tool":
        return []
    result = _parse_content(getattr(row, "content", None))
    if result is None or not _result_is_executed(row, result):
        return []
    metadata = _result_metadata(result)
    return [
        _ChangeCandidate(
            row=row,
            definition=definition,
            raw_diff=raw_diff,
            revision_id=revision_id,
            child_run=child_run,
            request_id=request_id,
        )
        for definition in _CHANGE_DEFINITIONS
        if (raw_diff := _as_record(metadata.get(definition.metadata_key))) is not None
    ]


def _number(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _normalize_line(value: object) -> AgentChangeLine | None:
    line = _as_record(value)
    if line is None:
        return None
    line_type: ChangeLineType = (
        "added"
        if line.get("type") == "added"
        else "removed"
        if line.get("type") == "removed"
        else "context"
    )
    text = line.get("text")
    return AgentChangeLine(
        type=line_type,
        before_line_number=_number(
            line.get("before_line_number", line.get("beforeLineNumber"))
        ),
        after_line_number=_number(
            line.get("after_line_number", line.get("afterLineNumber"))
        ),
        text=text if isinstance(text, str) else "",
    )


def _normalize_sections(raw_diff: dict[str, Any]) -> list[AgentChangeSection]:
    raw_sections = raw_diff.get("sections")
    if not isinstance(raw_sections, list):
        return []
    sections: list[AgentChangeSection] = []
    for raw_section in raw_sections:
        section = _as_record(raw_section)
        if section is None or section.get("type") not in {"content", "title"}:
            continue
        raw_lines = section.get("lines")
        lines = []
        if isinstance(raw_lines, list):
            lines = [
                line
                for raw_line in raw_lines
                if (line := _normalize_line(raw_line)) is not None
            ]
        sections.append(AgentChangeSection(type=section["type"], lines=lines))
    return sections


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalize_path(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split("/") if part.strip()]
    if not isinstance(value, list):
        return []
    return [part.strip() for part in value if isinstance(part, str) and part.strip()]


def _build_item(candidate: _ChangeCandidate) -> AgentChangeItem | None:
    row = candidate.row
    definition = candidate.definition
    raw_diff = candidate.raw_diff
    entity_id = _string(raw_diff.get(definition.id_field))
    title = next(
        (
            title
            for field in definition.title_fields
            if (title := _string(raw_diff.get(field))) is not None
        ),
        definition.kind,
    )
    fallback_key = f"{title}:{getattr(row, 'id', '')}"
    key = f"{definition.kind}:{entity_id or fallback_key}"
    sections = _normalize_sections(raw_diff)
    title_before_lines: list[str] = []
    title_after_lines: list[str] = []
    for section in sections:
        if section.type != "title":
            continue
        title_before_lines, title_after_lines = _section_state(section)
        break
    content_sections = [section for section in sections if section.type == "content"]
    operation = _string(raw_diff.get("operation")) or "update"
    added = sum(
        1
        for section in content_sections
        for line in section.lines
        if line.type == "added"
    )
    removed = sum(
        1
        for section in content_sections
        for line in section.lines
        if line.type == "removed"
    )
    child_run = candidate.child_run
    source: Literal["primary", "subagent"] = "subagent" if child_run else "primary"
    content_before: list[str] | None = None
    content_after: list[str] | None = None
    if operation == "create":
        content_before = []
        content_after = [
            line.text
            for section in content_sections
            for line in section.lines
            if line.type in {"context", "added"}
        ]
    return AgentChangeItem(
        key=key,
        kind=definition.kind,
        title=title,
        title_before="\n".join(title_before_lines) if title_before_lines else None,
        title_after="\n".join(title_after_lines) if title_after_lines else None,
        operation=operation,
        sections=content_sections,
        source_message_id=str(getattr(row, "id", "")),
        source=source,
        path=_normalize_path(raw_diff.get("path")),
        child_run_id=child_run.id if child_run else None,
        request_id=candidate.request_id,
        agent_key=child_run.agent_key if child_run else None,
        agent_number=get_child_run_agent_number(child_run.metadata_json) if child_run else None,
        revision_id=candidate.revision_id,
        added=added,
        removed=removed,
        _content_before=content_before,
        _content_after=content_after,
    )


def _section_state(section: AgentChangeSection) -> tuple[list[str], list[str]]:
    before: list[str] = []
    after: list[str] = []
    for line in section.lines:
        if line.type in {"context", "removed"}:
            before.append(line.text)
        if line.type in {"context", "added"}:
            after.append(line.text)
    return before, after


def _build_diff_lines(before: list[str], after: list[str]) -> list[AgentChangeLine]:
    lines: list[AgentChangeLine] = []
    matcher = SequenceMatcher(a=before, b=after, autojunk=False)
    before_line_number = 1
    after_line_number = 1
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(before_end - before_start):
                lines.append(
                    AgentChangeLine(
                        type="context",
                        before_line_number=before_line_number,
                        after_line_number=after_line_number,
                        text=before[before_start + offset],
                    )
                )
                before_line_number += 1
                after_line_number += 1
            continue
        if tag in {"delete", "replace"}:
            for text in before[before_start:before_end]:
                lines.append(
                    AgentChangeLine(
                        type="removed",
                        before_line_number=before_line_number,
                        after_line_number=None,
                        text=text,
                    )
                )
                before_line_number += 1
        if tag in {"insert", "replace"}:
            for text in after[after_start:after_end]:
                lines.append(
                    AgentChangeLine(
                        type="added",
                        before_line_number=None,
                        after_line_number=after_line_number,
                        text=text,
                    )
                )
                after_line_number += 1
    return lines


def _apply_content_patch(
    current: Sequence[str], sections: Sequence[AgentChangeSection]
) -> list[str] | None:
    """Apply a line-numbered partial Diff to a known current content state."""
    changed_lines = [
        line
        for section in sections
        for line in section.lines
        if line.type != "context"
    ]
    if not changed_lines:
        return list(current)

    removed_lines = [line for line in changed_lines if line.type == "removed"]
    if any(line.before_line_number is None for line in removed_lines):
        return None
    result = list(current)
    for line in sorted(
        removed_lines,
        key=lambda item: item.before_line_number or 0,
        reverse=True,
    ):
        index = (line.before_line_number or 0) - 1
        if index < 0 or index >= len(result) or result[index] != line.text:
            return None
        result.pop(index)

    added_lines = [line for line in changed_lines if line.type == "added"]
    if any(line.after_line_number is None for line in added_lines):
        return None
    for line in sorted(
        added_lines,
        key=lambda item: item.after_line_number or 0,
    ):
        index = (line.after_line_number or 0) - 1
        if index < 0 or index > len(result):
            return None
        result.insert(index, line.text)
    return result


def _content_sections_from_state(
    before: Sequence[str], after: Sequence[str]
) -> list[AgentChangeSection]:
    if list(before) == list(after):
        return []
    return [
        AgentChangeSection(
            type="content",
            lines=_build_diff_lines(list(before), list(after)),
        )
    ]


def _copy_item(item: AgentChangeItem) -> AgentChangeItem:
    return replace(item, sections=list(item.sections), path=list(item.path))


def _merge_sections(
    existing_sections: Sequence[AgentChangeSection],
    incoming_sections: Sequence[AgentChangeSection],
) -> list[AgentChangeSection]:
    states: dict[ChangeSectionType, tuple[list[str], list[str]]] = {}
    section_order: list[ChangeSectionType] = []
    for section in existing_sections:
        states[section.type] = _section_state(section)
        section_order.append(section.type)
    for section in incoming_sections:
        before, after = _section_state(section)
        if before == after:
            continue
        if section.type in states:
            states[section.type] = (states[section.type][0], after)
        else:
            states[section.type] = (before, after)
            section_order.append(section.type)
    return [
        AgentChangeSection(type=section_type, lines=_build_diff_lines(*states[section_type]))
        for section_type in section_order
        if states[section_type][0] != states[section_type][1]
    ]


def _merge_item(existing: AgentChangeItem, item: AgentChangeItem) -> None:
    merged_from_known_state = False
    if existing._content_before is not None and existing._content_after is not None:
        if item.operation == "delete":
            next_content = []
        elif item.operation == "create" and item._content_after is not None:
            next_content = list(item._content_after)
        else:
            next_content = _apply_content_patch(existing._content_after, item.sections)
        if next_content is not None:
            existing._content_after = next_content
            existing.sections = _content_sections_from_state(
                existing._content_before,
                next_content,
            )
            merged_from_known_state = True

    if not merged_from_known_state:
        existing.sections = _merge_sections(existing.sections, item.sections)
        existing._content_before = None
        existing._content_after = None
    if item.title_before is not None and existing.title_before is None:
        existing.title_before = item.title_before
    if item.title_after is not None:
        existing.title_after = item.title_after
    existing.added = sum(
        1
        for section in existing.sections
        for line in section.lines
        if line.type == "added"
    )
    existing.removed = sum(
        1
        for section in existing.sections
        for line in section.lines
        if line.type == "removed"
    )
    if item.operation == "delete":
        existing.operation = "delete"
    elif existing.operation != "create":
        existing.operation = item.operation
    if item.path or item.operation == "move":
        existing.path = item.path
    existing.source_message_id = item.source_message_id
    existing.source = item.source
    existing.child_run_id = item.child_run_id
    existing.request_id = item.request_id
    existing.agent_key = item.agent_key
    existing.agent_number = item.agent_number
    existing.revision_id = item.revision_id


def _summary_from_candidates(
    candidates: Sequence[_ChangeCandidate],
    *,
    source: Literal["primary", "subagent", "session"] | None = None,
    item_cache: dict[int, AgentChangeItem] | None = None,
) -> AgentChangeSummary:
    items_by_key: dict[str, AgentChangeItem] = {}
    first_operations: dict[str, str] = {}
    for candidate in candidates:
        item = item_cache.get(id(candidate)) if item_cache is not None else None
        if item is None:
            item = _build_item(candidate)
        if item is None:
            continue
        if source is not None:
            item = replace(item, source=source)
        existing = items_by_key.get(item.key)
        if existing is None:
            items_by_key[item.key] = _copy_item(item)
            first_operations[item.key] = item.operation
        else:
            _merge_item(existing, item)
    return AgentChangeSummary(
        items=[
            item
            for key, item in items_by_key.items()
            if not (
                first_operations.get(key) == "create"
                and item.operation == "delete"
                and not item.sections
            )
        ]
    )


def _combine_summaries(summaries: Sequence[AgentChangeSummary]) -> AgentChangeSummary:
    items_by_key: dict[str, AgentChangeItem] = {}
    first_operations: dict[str, str] = {}
    for summary in summaries:
        for item in summary.items:
            existing = items_by_key.get(item.key)
            if existing is None:
                items_by_key[item.key] = _copy_item(item)
                first_operations[item.key] = item.operation
            else:
                _merge_item(existing, item)
    return AgentChangeSummary(
        items=[
            item
            for key, item in items_by_key.items()
            if not (
                first_operations.get(key) == "create"
                and item.operation == "delete"
                and not item.sections
            )
        ]
    )


def _parent_revision_boundaries(
    parent_messages: Sequence[object],
    revisions: Sequence[Revision],
) -> list[tuple[int, str]]:
    boundaries: dict[int, str] = {}
    for row in parent_messages:
        if getattr(row, "role", None) != "user":
            continue
        revision_id = _string(_row_metadata(row).get("revision_id"))
        seq = getattr(row, "seq", None)
        if revision_id is not None and isinstance(seq, int):
            boundaries[seq] = revision_id
    for revision in revisions:
        if (
            revision.revision_type == "agent"
            and revision.status != "rolled_back"
            and revision.user_message_seq is not None
        ):
            boundaries.setdefault(revision.user_message_seq, revision.id)
    return sorted(boundaries.items())


def _revision_for_seq(boundaries: Sequence[tuple[int, str]], seq: int) -> str | None:
    if not boundaries:
        return None
    positions = [item[0] for item in boundaries]
    index = bisect_right(positions, seq) - 1
    return boundaries[index][1] if index >= 0 else None


def _request_for_seq(
    requests: Sequence[AgentChildRunRequest],
    seq: int,
) -> AgentChildRunRequest | None:
    eligible = [
        request
        for request in requests
        if request.status not in {"cancelled", "failed", "error"}
        if request.child_user_message_seq is not None
        and request.child_user_message_seq <= seq
    ]
    return (
        max(
            eligible,
            key=lambda request: (
                request.child_user_message_seq
                if request.child_user_message_seq is not None
                else -1,
                request.seq,
            ),
        )
        if eligible
        else None
    )


def build_agent_changes(
    session_id: str,
    *,
    parent_messages: Sequence[object],
    child_runs: Sequence[AgentChildRun],
    child_requests: Sequence[AgentChildRunRequest],
    child_messages: Sequence[object],
    revisions: Sequence[Revision],
) -> AgentSessionChanges:
    """Build a hierarchical change projection from persisted agent messages."""
    valid_revisions = {
        revision.id
        for revision in revisions
        if revision.revision_type == "agent"
        and revision.status != "rolled_back"
    }
    has_revision_rows = bool(revisions)
    parent_boundaries = _parent_revision_boundaries(parent_messages, revisions)
    parent_candidates: list[_ChangeCandidate] = []
    for row in parent_messages:
        row_seq = getattr(row, "seq", None)
        candidates = _extract_candidates(
            row,
            revision_id=_revision_for_seq(parent_boundaries, row_seq)
            if isinstance(row_seq, int)
            else None,
        )
        parent_candidates.extend(
            candidate
            for candidate in candidates
            if not has_revision_rows or candidate.revision_id in valid_revisions
        )

    runs_by_thread = {run.child_thread_id: run for run in child_runs}
    requests_by_run: dict[str, list[AgentChildRunRequest]] = defaultdict(list)
    for request in child_requests:
        requests_by_run[request.child_run_id].append(request)
    for requests in requests_by_run.values():
        requests.sort(key=lambda request: request.seq)

    child_candidates: list[_ChangeCandidate] = []
    for row in child_messages:
        child_run = runs_by_thread.get(str(getattr(row, "session_id", "")))
        if child_run is None:
            continue
        row_seq = getattr(row, "seq", None)
        if not isinstance(row_seq, int):
            continue
        request = _request_for_seq(
            requests_by_run.get(child_run.id, []),
            row_seq,
        )
        revision_id = (
            request.parent_revision_id
            if request is not None
            else child_run.parent_revision_id
        )
        candidates = _extract_candidates(
            row,
            revision_id=revision_id,
            child_run=child_run,
            request_id=request.id if request else None,
        )
        if has_revision_rows:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.revision_id is None or candidate.revision_id in valid_revisions
            ]
        child_candidates.extend(candidates)

    all_candidates = [*parent_candidates, *child_candidates]
    item_cache = {
        id(candidate): item
        for candidate in all_candidates
        if (item := _build_item(candidate)) is not None
    }
    candidates_by_revision: dict[str, list[_ChangeCandidate]] = defaultdict(list)
    for candidate in all_candidates:
        if candidate.revision_id is not None:
            candidates_by_revision[candidate.revision_id].append(candidate)

    ordered_revisions = sorted(
        (
            revision
            for revision in revisions
            if revision.id in valid_revisions
        ),
        key=lambda revision: (
            revision.user_message_seq if revision.user_message_seq is not None else 2**31,
            revision.created_at,
        ),
    )
    turns: list[AgentTurnChanges] = []
    for revision in ordered_revisions:
        revision_candidates = candidates_by_revision.get(revision.id, [])
        primary_candidates = [
            candidate for candidate in revision_candidates if candidate.child_run is None
        ]
        child_groups: dict[tuple[str, str | None], list[_ChangeCandidate]] = defaultdict(list)
        for candidate in revision_candidates:
            if candidate.child_run is not None:
                child_groups[(candidate.child_run.id, candidate.request_id)].append(candidate)

        subagent_runs: list[AgentSubagentRunChanges] = []
        child_summaries: list[AgentChangeSummary] = []
        for (child_run_id, request_id), candidates in child_groups.items():
            child_run = candidates[0].child_run
            if child_run is None:
                continue
            summary = _summary_from_candidates(candidates, item_cache=item_cache)
            if summary.item_count == 0:
                continue
            child_summaries.append(summary)
            subagent_runs.append(
                AgentSubagentRunChanges(
                    child_run_id=child_run_id,
                    child_thread_id=child_run.child_thread_id,
                    request_id=request_id,
                    child_user_message_id=(
                        next(
                            (
                                request.child_user_message_id
                                for request in requests_by_run.get(child_run_id, [])
                                if request.id == request_id
                            ),
                            None,
                        )
                        if request_id
                        else None
                    ),
                    agent_key=child_run.agent_key,
                    agent_number=get_child_run_agent_number(child_run.metadata_json),
                    changes=summary,
                )
            )

        turn_summary = _combine_summaries(
            [
                summary
                for summary in [
                    _summary_from_candidates(primary_candidates, item_cache=item_cache),
                    *child_summaries,
                ]
                if summary.item_count > 0
            ]
        )
        turns.append(
            AgentTurnChanges(
                revision_id=revision.id,
                user_message_id=revision.user_message_id,
                user_message_seq=revision.user_message_seq,
                changes=turn_summary,
                subagent_runs=subagent_runs,
            )
        )

    return AgentSessionChanges(
        session_id=session_id,
        turns=turns,
        session_changes=_summary_from_candidates(
            all_candidates,
            source="session",
            item_cache=item_cache,
        ),
    )


async def _list_descendant_child_runs(
    session: AsyncSession,
    parent_session_id: str,
) -> list[AgentChildRun]:
    runs_by_parent: dict[str, list[AgentChildRun]] = defaultdict(list)
    pending_parent_ids = [parent_session_id]
    seen_parent_ids = {parent_session_id}
    while pending_parent_ids:
        child_runs = await list_child_runs_for_parents(session, pending_parent_ids)
        next_parent_ids: list[str] = []
        for child_run in child_runs:
            runs_by_parent[child_run.parent_session_id].append(child_run)
            if child_run.child_thread_id not in seen_parent_ids:
                seen_parent_ids.add(child_run.child_thread_id)
                next_parent_ids.append(child_run.child_thread_id)
        pending_parent_ids = next_parent_ids

    descendants: list[AgentChildRun] = []
    expanded_parent_ids: set[str] = set()

    def append_descendants(current_parent_id: str) -> None:
        if current_parent_id in expanded_parent_ids:
            return
        expanded_parent_ids.add(current_parent_id)
        for child_run in runs_by_parent.get(current_parent_id, []):
            append_descendants(child_run.child_thread_id)
            descendants.append(child_run)

    append_descendants(parent_session_id)
    return descendants


async def load_agent_session_changes(
    session: AsyncSession,
    session_id: str,
) -> AgentSessionChanges:
    """Load and project all parent and descendant child-run changes."""
    child_runs = await _list_descendant_child_runs(session, session_id)
    message_by_session = await message_repo.list_by_sessions(
        session,
        [session_id, *(child_run.child_thread_id for child_run in child_runs)],
        roles=("user",),
        tool_names=_CHANGE_TOOL_NAMES,
    )
    parent_messages = message_by_session.get(session_id, [])
    child_requests: list[AgentChildRunRequest] = []
    if child_runs:
        result = await session.execute(
            select(AgentChildRunRequest)
            .where(
                col(AgentChildRunRequest.child_run_id).in_([run.id for run in child_runs])
            )
            .order_by(col(AgentChildRunRequest.child_run_id), col(AgentChildRunRequest.seq)),
        )
        child_requests = list(result.scalars().all())

    child_messages = [
        message
        for child_run in child_runs
        for message in message_by_session.get(child_run.child_thread_id, [])
    ]

    revision_result = await session.execute(
        select(Revision)
        .where(
            col(Revision.agent_session_id) == session_id,
            col(Revision.revision_type) == "agent",
        )
        .order_by(col(Revision.user_message_seq), col(Revision.created_at)),
    )
    revisions = list(revision_result.scalars().all())
    return build_agent_changes(
        session_id,
        parent_messages=parent_messages,
        child_runs=child_runs,
        child_requests=child_requests,
        child_messages=child_messages,
        revisions=revisions,
    )
