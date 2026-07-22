# -*- coding: utf-8 -*-
"""SkillReferenceDoc Service - 参考文档业务逻辑层。"""

from datetime import UTC, datetime
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.utils.tiktoken import count_tokens
from app.storage.models.skill_reference_doc import SkillReferenceDoc
from app.storage.repos import skill_reference_doc_repo
from app.storage.services import skill_service


async def _get_owned(session: AsyncSession, skill_db_id: str, doc_id: str) -> SkillReferenceDoc:
    doc = await skill_reference_doc_repo.get_by_id(session, doc_id)
    if doc is None or doc.skill_db_id != skill_db_id:
        raise NotFoundError(f"参考文档不存在: {doc_id}")
    return doc


async def _ensure_unique_title(
    session: AsyncSession,
    skill_db_id: str,
    title: str,
) -> str:
    existing = await skill_reference_doc_repo.list_by_skill(session, skill_db_id)
    existing_titles = {d.title for d in existing}
    if title not in existing_titles:
        return title
    base = title
    n = 2
    while f"{base} ({n})" in existing_titles:
        n += 1
    return f"{base} ({n})"


async def create_reference_doc(
    session: AsyncSession,
    skill_db_id: str,
    *,
    title: str = "",
    content: str = "",
) -> SkillReferenceDoc:
    skill = await skill_service.get_skill(session, skill_db_id)
    if skill_service.is_builtin_skill(skill):
        raise skill_service.SkillValidationError(f"不可编辑内置 Skill 的参考文档: {skill_db_id}")
    unique_title = await _ensure_unique_title(session, skill_db_id, title)
    doc = SkillReferenceDoc(
        skill_db_id=skill_db_id,
        title=unique_title,
        content=content,
        tokens=count_tokens(content),
    )
    return await skill_reference_doc_repo.create(session, doc)


async def list_reference_docs(
    session: AsyncSession,
    skill_db_id: str,
) -> Sequence[skill_service.SkillReferenceData]:
    return await skill_service.list_reference_docs(session, skill_db_id)


async def update_reference_doc(
    session: AsyncSession,
    skill_db_id: str,
    doc_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
) -> SkillReferenceDoc:
    skill = await skill_service.get_skill(session, skill_db_id)
    if skill_service.is_builtin_skill(skill):
        raise skill_service.SkillValidationError(f"不可编辑内置 Skill 的参考文档: {skill_db_id}")
    doc = await _get_owned(session, skill_db_id, doc_id)
    if title is not None and title != doc.title:
        existing = await skill_reference_doc_repo.list_by_skill(session, skill_db_id)
        if any(other.id != doc.id and other.title == title for other in existing):
            raise ConflictError(f"参考文档标题已存在: {title}")
        doc.title = title
    if content is not None:
        doc.content = content
        doc.tokens = count_tokens(content)
    doc.updated_at = datetime.now(UTC)
    return await skill_reference_doc_repo.update(session, doc)


async def delete_reference_doc(
    session: AsyncSession,
    skill_db_id: str,
    doc_id: str,
) -> None:
    skill = await skill_service.get_skill(session, skill_db_id)
    if skill_service.is_builtin_skill(skill):
        raise skill_service.SkillValidationError(f"不可编辑内置 Skill 的参考文档: {skill_db_id}")
    doc = await _get_owned(session, skill_db_id, doc_id)
    await skill_reference_doc_repo.delete(session, doc)
