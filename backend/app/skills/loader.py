"""从本地 YAML 文件加载内置 Skill。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from app.core.utils.tiktoken import count_tokens

SKILLS_DIR = Path(__file__).parent
BUILTIN_SKILL_ID_PREFIX = "builtin-skill--"


@dataclass(frozen=True)
class BuiltinSkillReference:
    """内置 Skill 的本地参考文档。"""

    id: str
    title: str
    content: str
    tokens: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class BuiltinSkill:
    """由 YAML 定义的内置 Skill。"""

    id: str
    name: str
    summary: str
    content: str
    is_enabled: bool
    references: tuple[BuiltinSkillReference, ...]
    created_at: datetime
    updated_at: datetime
    source: str = "builtin"


def _as_non_empty_string(data: object, field: str, yaml_path: Path) -> str | None:
    if isinstance(data, str) and data.strip():
        return data
    logger.warning(f"内置 Skill 配置字段无效: path={yaml_path}, field={field}")
    return None


def _load_builtin_skill(yaml_path: Path) -> BuiltinSkill | None:
    try:
        with yaml_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
        modified_at = datetime.fromtimestamp(yaml_path.stat().st_mtime, tz=UTC)
    except (OSError, yaml.YAMLError) as exc:
        logger.error(f"加载内置 Skill 配置失败: path={yaml_path}, error={exc}")
        return None

    if not isinstance(data, dict):
        logger.warning(f"内置 Skill 配置格式错误: path={yaml_path}")
        return None

    skill_id = _as_non_empty_string(data.get("id"), "id", yaml_path)
    name = _as_non_empty_string(data.get("name"), "name", yaml_path)
    summary = _as_non_empty_string(data.get("summary"), "summary", yaml_path)
    content = _as_non_empty_string(data.get("content"), "content", yaml_path)
    if not skill_id or not name or not summary or not content:
        return None
    if not skill_id.startswith(BUILTIN_SKILL_ID_PREFIX):
        logger.warning(f"内置 Skill ID 前缀无效: path={yaml_path}, id={skill_id}")
        return None

    is_enabled = data.get("is_enabled", True)
    if not isinstance(is_enabled, bool):
        logger.warning(f"内置 Skill 启用状态无效: path={yaml_path}, id={skill_id}")
        return None

    raw_references = data.get("references", [])
    if not isinstance(raw_references, list):
        logger.warning(f"内置 Skill 参考文档格式错误: path={yaml_path}, id={skill_id}")
        return None

    references: list[BuiltinSkillReference] = []
    titles: set[str] = set()
    for index, raw_reference in enumerate(raw_references):
        if not isinstance(raw_reference, dict):
            logger.warning(f"内置 Skill 参考文档格式错误: path={yaml_path}, index={index}")
            return None
        title = _as_non_empty_string(raw_reference.get("name"), "references.name", yaml_path)
        reference_content = _as_non_empty_string(
            raw_reference.get("content"), "references.content", yaml_path
        )
        if not title or not reference_content:
            return None
        if title in titles:
            logger.warning(f"内置 Skill 参考文档名称重复: path={yaml_path}, title={title}")
            return None
        titles.add(title)
        references.append(
            BuiltinSkillReference(
                id=f"{skill_id}--reference--{index + 1}",
                title=title,
                content=reference_content,
                tokens=count_tokens(reference_content),
                created_at=modified_at,
                updated_at=modified_at,
            )
        )

    return BuiltinSkill(
        id=skill_id,
        name=name,
        summary=summary,
        content=content,
        is_enabled=is_enabled,
        references=tuple(references),
        created_at=modified_at,
        updated_at=modified_at,
    )


def load_builtin_skills() -> tuple[BuiltinSkill, ...]:
    """加载全部有效的内置 Skill，单个错误文件不会影响其余 Skill。"""
    if not SKILLS_DIR.exists():
        return ()

    skills: list[BuiltinSkill] = []
    ids: set[str] = set()
    for yaml_path in sorted(SKILLS_DIR.glob("*.yaml")):
        skill = _load_builtin_skill(yaml_path)
        if skill is None:
            continue
        if skill.id in ids:
            logger.warning(f"内置 Skill ID 重复: path={yaml_path}, id={skill.id}")
            continue
        ids.add(skill.id)
        skills.append(skill)
    return tuple(skills)


def load_builtin_skill(skill_id: str) -> BuiltinSkill | None:
    """按固定 ID 读取单个内置 Skill。"""
    if not skill_id.startswith(BUILTIN_SKILL_ID_PREFIX):
        return None
    filename = skill_id.removeprefix(BUILTIN_SKILL_ID_PREFIX)
    if not filename or Path(filename).name != filename:
        return None
    skill = _load_builtin_skill(SKILLS_DIR / f"{filename}.yaml")
    return skill if skill is not None and skill.id == skill_id else None
