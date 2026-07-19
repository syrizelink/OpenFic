"""内置 Skill YAML 资源加载。"""

from app.skills.loader import (
    BUILTIN_SKILL_ID_PREFIX,
    BuiltinSkill,
    BuiltinSkillReference,
    load_builtin_skill,
    load_builtin_skills,
)

__all__ = [
    "BUILTIN_SKILL_ID_PREFIX",
    "BuiltinSkill",
    "BuiltinSkillReference",
    "load_builtin_skill",
    "load_builtin_skills",
]
