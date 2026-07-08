# -*- coding: utf-8 -*-

import io
import zipfile

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_skills(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "测试技能",
            "summary": "简述",
            "content": "技能内容",
            "is_enabled": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试技能"
    assert data["is_enabled"] is True
    assert data["is_complete"] is True
    assert "skill_id" not in data

    list_response = await client.get("/api/v1/skills")
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_create_skill_with_empty_name(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "",
            "summary": "",
            "content": "",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == ""
    assert data["is_complete"] is False
    assert data["is_enabled"] is False


@pytest.mark.asyncio
async def test_incomplete_skill_cannot_be_enabled(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "测试技能",
            "summary": "",
            "content": "",
            "is_enabled": True,
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_toggle_skill(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/skills",
        json={
            "name": "测试技能",
            "summary": "简述",
            "content": "技能内容",
        },
    )
    skill_db_id = create_response.json()["id"]

    toggle_response = await client.post(f"/api/v1/skills/{skill_db_id}/toggle")
    assert toggle_response.status_code == 200
    assert toggle_response.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_create_skill_dedupes_duplicate_name(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/skills",
        json={"name": "新建技能", "summary": "", "content": ""},
    )
    assert first.status_code == 201
    assert first.json()["name"] == "新建技能"

    second = await client.post(
        "/api/v1/skills",
        json={"name": "新建技能", "summary": "", "content": ""},
    )
    assert second.status_code == 201
    assert second.json()["name"] == "新建技能 (2)"

    third = await client.post(
        "/api/v1/skills",
        json={"name": "新建技能", "summary": "", "content": ""},
    )
    assert third.status_code == 201
    assert third.json()["name"] == "新建技能 (3)"


@pytest.mark.asyncio
async def test_update_skill_name_conflict(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/skills",
        json={"name": "技能一", "summary": "", "content": ""},
    )
    create_b = await client.post(
        "/api/v1/skills",
        json={"name": "技能二", "summary": "", "content": ""},
    )
    skill_b_id = create_b.json()["id"]

    conflict = await client.patch(
        f"/api/v1/skills/{skill_b_id}",
        json={"name": "技能一"},
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_update_skill_keeps_same_name(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/skills",
        json={"name": "技能", "summary": "", "content": ""},
    )
    skill_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/skills/{skill_id}",
        json={"name": "技能", "summary": "新简述"},
    )
    assert update_response.status_code == 200


SKILL_MD = """---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
---

# PDF Processing

Step 1: extract text.
"""

REFERENCE_MD = "# Reference\n\nDetail here.\n"


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_single_md_recognized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("note.md", SKILL_MD.encode(), "text/markdown"))],
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_recognized"] is True
    assert data["skill"]["name"] == "pdf-processing"
    assert data["skill"]["summary"].startswith("Extract PDF text")
    assert "Step 1" in data["skill"]["content"]
    assert data["reference_docs"] == []


@pytest.mark.asyncio
async def test_import_single_md_unrecognized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("notes.md", b"just some plain text no frontmatter", "text/markdown"))],
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_recognized"] is False
    assert data["skill"]["name"] == "notes"
    assert data["skill"]["content"] == "just some plain text no frontmatter"


@pytest.mark.asyncio
async def test_import_zip_with_references(client: AsyncClient) -> None:
    zip_bytes = _make_zip(
        {
            "my-skill/SKILL.md": SKILL_MD,
            "my-skill/references/REFERENCE.md": REFERENCE_MD,
            "my-skill/references/forms.md": "# Forms\n\nform content\n",
        }
    )
    response = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("skill.zip", zip_bytes, "application/zip"))],
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_recognized"] is True
    assert data["skill"]["name"] == "pdf-processing"
    titles = sorted(d["title"] for d in data["reference_docs"])
    assert titles == ["REFERENCE", "forms"]
    assert all(d["tokens"] > 0 for d in data["reference_docs"])


@pytest.mark.asyncio
async def test_import_zip_without_skill_md(client: AsyncClient) -> None:
    zip_bytes = _make_zip({"readme.md": "no skill here"})
    response = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("bad.zip", zip_bytes, "application/zip"))],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_import_unsupported_file_type(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("file.txt", b"plain", "text/plain"))],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_import_skill_name_dedup(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("note.md", SKILL_MD.encode(), "text/markdown"))],
    )
    assert first.status_code == 201
    assert first.json()["skill"]["name"] == "pdf-processing"

    second = await client.post(
        "/api/v1/skills/import",
        files=[("files", ("note.md", SKILL_MD.encode(), "text/markdown"))],
    )
    assert second.status_code == 201
    assert second.json()["skill"]["name"] == "pdf-processing (2)"