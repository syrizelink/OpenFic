"""Collaboration opt-in, persistence and legacy-write isolation."""

import base64

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.collaboration import service
from app.core.errors import ConflictError
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo, setting_repo
from app.storage.services import chapter_service


async def make_chapter(session):
    project = Project(title="Collaboration")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="Volume", order=1)
    session.add(volume)
    await session.flush()
    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Chapter",
        content="original",
        order=1,
    )
    return await chapter_repo.create(session, chapter)


async def test_collaboration_is_disabled_by_default(session: AsyncSession):
    assert not await service.is_enabled(session)
    chapter = await make_chapter(session)
    updated = await chapter_service.update_chapter(
        session, chapter.id, content="legacy edit"
    )
    assert updated.content == "legacy edit"


async def test_binary_and_snapshot_persist_together_and_ignore_stale_versions(
    session: AsyncSession,
):
    chapter = await make_chapter(session)
    await setting_repo.upsert(session, service.SETTING_KEY, "true")
    record = await service.document_record(session, chapter.id)
    data = {
        "room": service.room_for(record),
        "state": base64.b64encode(b"binary-2").decode(),
        "version": 2,
        "content": "new text",
    }
    await service.persist_document(session, data)
    await service.persist_document(session, {**data, "version": 1, "content": "stale"})
    assert chapter.content == "new text"
    assert record.state == b"binary-2"
    assert record.version == 2


async def test_legacy_content_writes_are_rejected_but_titles_remain_available(
    session: AsyncSession,
):
    chapter = await make_chapter(session)
    await setting_repo.upsert(session, service.SETTING_KEY, "true")
    updated = await chapter_service.update_chapter(session, chapter.id, title="renamed")
    assert updated.title == "renamed"
    with pytest.raises(ConflictError):
        await chapter_service.update_chapter(
            session, chapter.id, content="stale full text"
        )


async def test_disabled_legacy_edit_invalidates_old_yjs_identity(session: AsyncSession):
    chapter = await make_chapter(session)
    record = await service.document_record(session, chapter.id)
    old_epoch = record.epoch
    chapter.content = "legacy text changed"
    await chapter_repo.update_chapter(session, chapter)
    replacement = await service.document_record(session, chapter.id)
    assert replacement.epoch != old_epoch
    with pytest.raises(ConflictError):
        await service.load_document(session, f"{chapter.id}:{old_epoch}")


async def test_legacy_stale_version_cannot_overwrite_latest_snapshot(
    session: AsyncSession,
):
    chapter = await make_chapter(session)
    previous = chapter.updated_at
    await chapter_service.update_chapter(session, chapter.id, content="newer text")
    with pytest.raises(ConflictError):
        await chapter_service.update_chapter(
            session, chapter.id, content="old text", expected_updated_at=previous
        )
    assert chapter.content == "newer text"


async def test_settings_opt_in_is_persisted_only_after_worker_starts(
    client, monkeypatch
):
    from unittest.mock import AsyncMock

    initial = await client.get("/api/v1/settings")
    assert initial.json()["human_ai_collaboration"] is False
    call = AsyncMock(side_effect=ConflictError("Node unavailable"))
    monkeypatch.setattr(service.worker, "call", call)
    rejected = await client.patch(
        "/api/v1/settings", json={"human_ai_collaboration": True}
    )
    assert rejected.status_code == 409
    assert (await client.get("/api/v1/settings")).json()[
        "human_ai_collaboration"
    ] is False
    call.side_effect = None
    call.return_value = True
    enabled = await client.patch(
        "/api/v1/settings", json={"human_ai_collaboration": True}
    )
    assert enabled.status_code == 200
    assert enabled.json()["human_ai_collaboration"] is True
