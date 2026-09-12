# -*- coding: utf-8 -*-
"""Uji lapisan layanan note_service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.note import Note
from app.storage.models.project import Project
from app.storage.repos import note_category_repo, note_repo
from app.storage.services import note_service


async def _create_project(session: AsyncSession) -> Project:
    project = Project(title="Proyek Uji", description="")
    session.add(project)
    await session.flush()
    return project


@pytest.mark.asyncio
async def test_create_note_at_root_level(session: AsyncSession) -> None:
    project = await _create_project(session)
    note = await note_service.create_note(
        session, project.id, category_id=None, title="Catatan Akar", content="Isi"
    )
    assert note.id is not None
    assert note.project_id == project.id
    assert note.category_id is None
    assert note.title == "Catatan Akar"
    assert note.content == "Isi"


@pytest.mark.asyncio
async def test_create_note_in_first_level_category(session: AsyncSession) -> None:
    project = await _create_project(session)
    cat = await note_service.create_category(
        session, project.id, parent_id=None, title="Kategori Tingkat Satu"
    )
    note = await note_service.create_note(
        session, project.id, category_id=cat.id, title="Catatan Anak", content=""
    )
    assert note.category_id == cat.id


@pytest.mark.asyncio
async def test_create_note_in_second_level_category(session: AsyncSession) -> None:
    project = await _create_project(session)
    parent = await note_service.create_category(
        session, project.id, parent_id=None, title="Tingkat Satu"
    )
    child = await note_service.create_category(
        session, project.id, parent_id=parent.id, title="Tingkat Dua"
    )
    note = await note_service.create_note(
        session, project.id, category_id=child.id, title="Catatan di Tingkat Dua", content=""
    )
    assert note.category_id == child.id


@pytest.mark.asyncio
async def test_create_category_third_level_rejected(session: AsyncSession) -> None:
    project = await _create_project(session)
    parent = await note_service.create_category(
        session, project.id, parent_id=None, title="Tingkat Satu"
    )
    child = await note_service.create_category(
        session, project.id, parent_id=parent.id, title="Tingkat Dua"
    )
    with pytest.raises(ValueError, match="tidak boleh lebih dari dua"):
        await note_service.create_category(
            session, project.id, parent_id=child.id, title="Tingkat Tiga"
        )


@pytest.mark.asyncio
async def test_move_category_self_reference_rejected(session: AsyncSession) -> None:
    project = await _create_project(session)
    cat = await note_service.create_category(
        session, project.id, parent_id=None, title="Kategori A"
    )
    with pytest.raises(ValueError, match="dirinya sendiri atau ke turunannya"):
        await note_service.move_item(session, "category", cat.id, cat.id)


@pytest.mark.asyncio
async def test_move_category_descendant_reference_rejected(
    session: AsyncSession,
) -> None:
    project = await _create_project(session)
    parent = await note_service.create_category(
        session, project.id, parent_id=None, title="Induk"
    )
    child = await note_service.create_category(
        session, project.id, parent_id=parent.id, title="Anak"
    )
    with pytest.raises(ValueError, match="dirinya sendiri atau ke turunannya"):
        await note_service.move_item(session, "category", parent.id, child.id)


@pytest.mark.asyncio
async def test_move_category_second_level_to_root(session: AsyncSession) -> None:
    project = await _create_project(session)
    parent = await note_service.create_category(
        session, project.id, parent_id=None, title="Tingkat Satu"
    )
    child = await note_service.create_category(
        session, project.id, parent_id=parent.id, title="Tingkat Dua"
    )
    moved = await note_service.move_item(session, "category", child.id, None)
    assert moved.parent_id is None


@pytest.mark.asyncio
async def test_hidden_notes_not_returned_in_list_notes_tool_mode(
    session: AsyncSession,
) -> None:
    project = await _create_project(session)
    hidden_note = Note(
        project_id=project.id,
        category_id=None,
        title="Catatan Tersembunyi",
        content="",
        is_hidden=True,
    )
    session.add(hidden_note)
    await session.flush()
    visible_notes = await note_repo.list_by_project(
        session, project.id, include_hidden=False
    )
    assert all(n.is_hidden is False for n in visible_notes)


@pytest.mark.asyncio
async def test_list_notes_tree_structure(session: AsyncSession) -> None:
    project = await _create_project(session)
    cat1 = await note_service.create_category(session, project.id, None, "Kategori A")
    cat2 = await note_service.create_category(session, project.id, cat1.id, "Kategori A - Anak")
    await note_service.create_note(session, project.id, None, "Catatan Akar", "x")
    await note_service.create_note(session, project.id, cat1.id, "Catatan A", "x")
    await note_service.create_note(session, project.id, cat2.id, "Catatan A - Anak", "x")

    result = await note_service.list_notes(session, project.id)
    assert result.total_notes == 3
    assert len(result.root_notes) == 1
    assert result.root_notes[0].title == "Catatan Akar"
    assert len(result.categories) == 1
    assert result.categories[0].category.title == "Kategori A"
    assert len(result.categories[0].sub_categories) == 1
    assert result.categories[0].sub_categories[0].category.title == "Kategori A - Anak"
    assert len(result.categories[0].notes) == 1
    assert result.categories[0].notes[0].title == "Catatan A"


@pytest.mark.asyncio
async def test_delete_category_cascades_to_children(session: AsyncSession) -> None:
    project = await _create_project(session)
    parent = await note_service.create_category(session, project.id, None, "Induk")
    child = await note_service.create_category(session, project.id, parent.id, "Anak")
    await note_service.create_note(session, project.id, child.id, "Catatan", "")
    assert await note_category_repo.get_by_id(session, parent.id) is not None
    await note_service.delete_category(session, parent.id)
    assert await note_category_repo.get_by_id(session, parent.id) is None
    assert await note_category_repo.get_by_id(session, child.id) is None
