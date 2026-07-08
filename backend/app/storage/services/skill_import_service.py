# -*- coding: utf-8 -*-
"""Skill Import Service - 按 Agent Skills 规范导入技能与参考文档。

参考: https://agentskills.io/specification
- 单个 Markdown 文件: 解析 YAML frontmatter（name/description），Body 作为内容。
- 压缩包 / 文件夹: 定位 SKILL.md 并解析，references/ 下的 Markdown 作为参考文档。
"""

import io
import posixpath
import zipfile
from dataclasses import dataclass

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.skill import Skill
from app.storage.models.skill_reference_doc import SkillReferenceDoc
from app.storage.services import skill_reference_doc_service, skill_service


class SkillImportError(Exception):
    """技能导入解析失败。"""


@dataclass
class UploadedFile:
    """存储层用的上传文件数据，不依赖 FastAPI。"""

    filename: str
    content: bytes


@dataclass
class ParsedSkill:
    name: str
    summary: str
    content: str
    recognized: bool


@dataclass
class ImportResult:
    skill: Skill
    reference_docs: list[SkillReferenceDoc]
    recognized: bool


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """拆分 YAML frontmatter，返回 (frontmatter_dict, body)。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, body


def _is_recognized(frontmatter: dict) -> bool:
    name = frontmatter.get("name")
    desc = frontmatter.get("description")
    return (
        isinstance(name, str)
        and bool(name.strip())
        and isinstance(desc, str)
        and bool(desc.strip())
    )


def _normalize_path(filename: str) -> str:
    return filename.replace("\\", "/").lstrip("./")


def _decode(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _parse_single_md(text: str, filename: str) -> ParsedSkill:
    frontmatter, body = _split_frontmatter(text)
    if _is_recognized(frontmatter):
        return ParsedSkill(
            name=str(frontmatter["name"]).strip(),
            summary=str(frontmatter["description"]).strip(),
            content=body,
            recognized=True,
        )
    stem = posixpath.splitext(posixpath.basename(_normalize_path(filename)))[0]
    return ParsedSkill(name=stem, summary="", content=text, recognized=False)


def _extract_zip(content: bytes) -> dict[str, str]:
    """解压 zip，返回 相对路径 -> 文本内容。"""
    result: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            path = _normalize_path(info.filename)
            if posixpath.basename(path) == "":
                continue
            result[path] = zf.read(info).decode("utf-8", errors="replace")
    return result


def _find_skill_md(file_map: dict[str, str]) -> str | None:
    candidates = [p for p in file_map if posixpath.basename(p) == "SKILL.md"]
    if not candidates:
        return None
    # 优先选最浅层级的 SKILL.md
    candidates.sort(key=lambda p: (p.count("/"), len(p)))
    return candidates[0]


def _collect_references(file_map: dict[str, str], root: str) -> list[tuple[str, str]]:
    """收集 root/references/ 下的 Markdown 文档，返回 (标题, 内容) 列表。"""
    ref_prefix = f"{root}/references/" if root else "references/"
    refs: list[tuple[str, str]] = []
    for path in sorted(file_map):
        if not path.startswith(ref_prefix):
            continue
        if not path.lower().endswith(".md"):
            continue
        title = posixpath.splitext(posixpath.basename(path))[0]
        refs.append((title, file_map[path]))
    return refs


def _parse_skill_md(text: str, root: str) -> ParsedSkill:
    frontmatter, body = _split_frontmatter(text)
    if _is_recognized(frontmatter):
        return ParsedSkill(
            name=str(frontmatter["name"]).strip(),
            summary=str(frontmatter["description"]).strip(),
            content=body,
            recognized=True,
        )
    root_name = posixpath.basename(root.rstrip("/")) if root else "导入技能"
    return ParsedSkill(name=root_name, summary="", content=text, recognized=False)


async def import_skill(
    session: AsyncSession,
    files: list[UploadedFile],
) -> ImportResult:
    """解析上传文件并创建技能与参考文档（单事务，原子）。"""
    if not files:
        raise SkillImportError("未选择文件")

    if len(files) != 1:
        raise SkillImportError("仅支持单个文件导入")

    single = files[0]
    name = _normalize_path(single.filename)
    lower = name.lower()

    if "/" not in name and lower.endswith(".md"):
        parsed = _parse_single_md(_decode(single.content), single.filename)
        ref_texts: list[tuple[str, str]] = []
    elif lower.endswith(".zip"):
        file_map = _extract_zip(single.content)
        skill_md = _find_skill_md(file_map)
        if skill_md is None:
            raise SkillImportError("压缩包内未找到 SKILL.md")
        root = posixpath.dirname(skill_md)
        parsed = _parse_skill_md(file_map[skill_md], root)
        ref_texts = _collect_references(file_map, root)
    else:
        raise SkillImportError("不支持的文件类型，仅支持 .md / .zip")

    skill = await skill_service.create_skill(
        session,
        name=parsed.name,
        summary=parsed.summary,
        content=parsed.content,
        is_enabled=False,
    )
    docs: list[SkillReferenceDoc] = []
    for title, content in ref_texts:
        doc = await skill_reference_doc_service.create_reference_doc(
            session,
            skill.id,
            title=title,
            content=content,
        )
        docs.append(doc)

    return ImportResult(skill=skill, reference_docs=docs, recognized=parsed.recognized)