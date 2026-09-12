# -*- coding: utf-8 -*-
"""Registrasi, pemuatan prompt bawaan, dan pengelolaan berkas agen kustom."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from app.storage.services.prompt_chain_service import PromptEntryData

PROMPTS_DIR = Path(__file__).parent
_BUILTIN_AGENT_NAMES = (
    "build",
    "plan",
    "explore",
    "composer",
    "auditor",
    "writer",
    "actor",
    "reviewer",
)


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    category_id: str
    label_key: str
    yaml_path: Path


_PROMPT_DEFINITIONS = (
    PromptDefinition(
        "session-title",
        "session",
        "sessionTitle",
        PROMPTS_DIR / "session" / "title.yaml",
    ),
    PromptDefinition(
        "session-compaction",
        "session",
        "sessionCompaction",
        PROMPTS_DIR / "session" / "compaction.yaml",
    ),
    PromptDefinition(
        "memory-chapter-summary",
        "memory",
        "memoryChapterSummary",
        PROMPTS_DIR / "memory" / "chapter-summary.yaml",
    ),
    PromptDefinition(
        "memory-range-summary",
        "memory",
        "memoryRangeSummary",
        PROMPTS_DIR / "memory" / "range-summary.yaml",
    ),
    *(
        PromptDefinition(
            f"builtin-agent--{agent_name}",
            "builtin-agents",
            f"builtinAgent{''.join(part.title() for part in agent_name.split('-'))}",
            PROMPTS_DIR / "builtin-agents" / f"{agent_name}.yaml",
        )
        for agent_name in _BUILTIN_AGENT_NAMES
    ),
)
_PROMPT_DEFINITION_BY_ID = {
    definition.prompt_id: definition for definition in _PROMPT_DEFINITIONS
}
_CATEGORY_DEFINITIONS = (
    ("session", "session"),
    ("memory", "memory"),
    ("builtin-agents", "builtinAgents"),
    ("custom-agents", "customAgents"),
)


def builtin_agent_prompt_id(agent_name: str) -> str:
    return f"builtin-agent--{agent_name}"


def custom_agent_prompt_id(agent_name: str) -> str:
    return f"custom-agent--{agent_name}"


def _get_yaml_path(prompt_id: str) -> Path | None:
    definition = _PROMPT_DEFINITION_BY_ID.get(prompt_id)
    if definition:
        return definition.yaml_path
    if prompt_id.startswith("custom-agent--"):
        agent_name = prompt_id.removeprefix("custom-agent--")
        return PROMPTS_DIR / "custom-agents" / f"{agent_name}.yaml" if agent_name else None
    return None


def load_prompt_chain(prompt_id: str) -> list[PromptEntryData] | None:
    """Memuat entri bawaan dari berkas YAML yang sesuai dengan ID prompt tertentu."""
    yaml_path = _get_yaml_path(prompt_id)
    if yaml_path is None or not yaml_path.exists():
        logger.warning(f"Berkas konfigurasi prompt tidak ditemukan: {yaml_path or prompt_id}")
        return None

    try:
        with yaml_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except (OSError, yaml.YAMLError) as exc:
        logger.error(f"Gagal memuat konfigurasi prompt: {yaml_path}, error: {exc}")
        return None

    if not data or "entries" not in data:
        logger.warning(f"Format konfigurasi prompt salah: {yaml_path}")
        return None

    return [
        PromptEntryData(
            name=entry.get("name", ""),
            role=entry.get("role", "user"),
            content=entry.get("content", ""),
            order_index=entry.get("order_index", 0),
            is_enabled=entry.get("is_enabled", True),
            token_count=entry.get("token_count", 0),
        )
        for entry in data["entries"]
    ]


def get_prompt_chains_metadata(
    custom_agents: list[tuple[str, str]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Mengembalikan metadata prompt satu tingkat yang dikelompokkan per kategori bisnis."""
    prompts_by_category = {
        category_id: [
            {
                "id": definition.prompt_id,
                "label_key": definition.label_key,
                "label": None,
            }
            for definition in _PROMPT_DEFINITIONS
            if definition.category_id == category_id
        ]
        for category_id, _ in _CATEGORY_DEFINITIONS
    }
    for key, display_name in sorted(custom_agents or [], key=lambda item: item[1].casefold()):
        prompts_by_category["custom-agents"].append(
            {
                "id": custom_agent_prompt_id(key),
                "label_key": "customAgent",
                "label": display_name,
            }
        )

    return {
        "categories": [
            {
                "id": category_id,
                "label_key": label_key,
                "prompts": prompts_by_category[category_id],
            }
            for category_id, label_key in _CATEGORY_DEFINITIONS
        ]
    }


_PRIMARY_AGENT_DEFAULT_CONTENT = """entries:
  - name: system_prompt
    role: system
    content: |
      Kamu adalah agen utama yang bertugas mengoordinasikan dan menjadwalkan sub-agen untuk
      menyelesaikan tugas yang kompleks. Rencanakan dan delegasikan pekerjaan sesuai kebutuhan
      tugas.
    order_index: 0
    is_enabled: true
    token_count: 0
  - name: user_prompt
    role: user
    content: |
      Silakan mulai menjalankan tugas.
    order_index: 1
    is_enabled: true
    token_count: 0
"""

_SUBAGENT_DEFAULT_CONTENT = """entries:
  - name: system_prompt
    role: system
    content: |
      Kamu adalah sub-agen yang bertugas menjalankan tugas spesifik yang didelegasikan oleh agen
      utama. Fokuslah menyelesaikan pekerjaan yang sedang diberikan.
    order_index: 0
    is_enabled: true
    token_count: 0
  - name: user_prompt
    role: user
    content: |
      Silakan mulai menjalankan tugas.
    order_index: 1
    is_enabled: true
    token_count: 0
"""


def create_custom_agent_prompt_yaml(
    agent_name: str,
    kind: str = "subagent",
    content: str | None = None,
) -> Path:
    """Membuat berkas YAML prompt bawaan untuk agen kustom."""
    yaml_path = _get_yaml_path(custom_agent_prompt_id(agent_name))
    if yaml_path is None:
        raise ValueError(f"Identitas agen kustom tidak valid: {agent_name}")
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(
        content or (_PRIMARY_AGENT_DEFAULT_CONTENT if kind == "primary" else _SUBAGENT_DEFAULT_CONTENT),
        encoding="utf-8",
    )
    logger.info(f"YAML prompt agen kustom sudah dibuat: {yaml_path}")
    return yaml_path


def delete_custom_agent_prompt_yaml(agent_name: str) -> bool:
    """Menghapus berkas YAML prompt agen kustom."""
    yaml_path = _get_yaml_path(custom_agent_prompt_id(agent_name))
    if yaml_path is None or not yaml_path.exists():
        return False
    yaml_path.unlink()
    logger.info(f"YAML prompt agen kustom sudah dihapus: {yaml_path}")
    return True


def reset_custom_agent_prompt_yaml(agent_name: str, kind: str = "subagent") -> Path:
    """Mereset YAML prompt agen kustom."""
    delete_custom_agent_prompt_yaml(agent_name)
    return create_custom_agent_prompt_yaml(agent_name, kind)
