# -*- coding: utf-8 -*-
"""
Prompt YAML Loader - 从 prompts 目录加载默认提示词配置。
"""

from pathlib import Path

import yaml
from loguru import logger

from app.storage.services.prompt_chain_service import PromptEntryData

PROMPTS_DIR = Path(__file__).parent
_BUILTIN_ASSISTANT_AGENT_NAMES = frozenset(
    ("primary", "explorer", "composer", "auditor", "writer", "actor", "reviewer")
)


def load_prompt_chain(
    mode_name: str,
    task_name: str,
    agent_name: str | None = None,
) -> list[PromptEntryData] | None:
    """
    从 YAML 文件加载默认提示词条目。
    
    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: Agent 名称（可选）。
    
    Returns:
        默认提示词条目列表，如果文件不存在则返回 None。
    """
    yaml_path = _get_yaml_path(mode_name, task_name, agent_name)
    
    if not yaml_path.exists():
        logger.warning(f"提示词配置文件不存在: {yaml_path}")
        return None
    
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data or "entries" not in data:
            logger.warning(f"提示词配置格式错误: {yaml_path}")
            return None
        
        entries = []
        for entry in data["entries"]:
            entries.append(
                PromptEntryData(
                    name=entry.get("name", ""),
                    role=entry.get("role", "user"),
                    content=entry.get("content", ""),
                    order_index=entry.get("order_index", 0),
                    is_enabled=entry.get("is_enabled", True),
                    token_count=entry.get("token_count", 0),
                )
            )
        
        return entries
    
    except Exception as e:
        logger.error(f"加载提示词配置失败: {yaml_path}, error: {e}")
        return None


def get_prompt_chains_metadata(
    db_agent_keys: list[str] | None = None,
) -> dict:
    """
    从 prompts 目录扫描所有 YAML 文件，生成元数据。

    返回分层结构: mode > task > agent

    Args:
        db_agent_keys: 从数据库 agent_definitions 表中获取的自定义 agent key 列表，
                       会合入 assistant/agent 下。
    """
    modes_dict: dict[str, dict] = {}

    if not PROMPTS_DIR.exists():
        return {"modes": []}

    for mode_dir in sorted(PROMPTS_DIR.iterdir()):
        if not mode_dir.is_dir() or mode_dir.name.startswith("_"):
            continue

        mode_name = mode_dir.name
        modes_dict[mode_name] = {
            "value": mode_name,
            "tasks": {},
        }

        for item in sorted(mode_dir.iterdir()):
            if item.name.startswith("_"):
                continue

            if item.is_dir():
                task_name = item.name
                if task_name not in modes_dict[mode_name]["tasks"]:
                    modes_dict[mode_name]["tasks"][task_name] = {
                        "value": task_name,
                        "agents": [],
                    }
                for agent_file in sorted(item.iterdir()):
                    if not agent_file.is_file() or agent_file.suffix != ".yaml":
                        continue
                    agent_name = agent_file.stem
                    if (
                        mode_name == "assistant"
                        and task_name == "agent"
                        and agent_name not in _BUILTIN_ASSISTANT_AGENT_NAMES
                    ):
                        continue
                    modes_dict[mode_name]["tasks"][task_name]["agents"].append({
                        "value": agent_name,
                    })
            elif item.is_file() and item.suffix == ".yaml":
                task_name = item.stem
                modes_dict[mode_name]["tasks"][task_name] = {
                    "value": task_name,
                    "agents": [],
                }

    if db_agent_keys:
        if "assistant" not in modes_dict:
            modes_dict["assistant"] = {"value": "assistant", "tasks": {}}
        if "agent" not in modes_dict["assistant"]["tasks"]:
            modes_dict["assistant"]["tasks"]["agent"] = {
                "value": "agent",
                "agents": [],
            }

        existing_agents: set[str] = set()
        for entry in modes_dict["assistant"]["tasks"]["agent"]["agents"]:
            existing_agents.add(entry["value"])
        for key in sorted(db_agent_keys):
            if key not in existing_agents:
                modes_dict["assistant"]["tasks"]["agent"]["agents"].append(
                    {"value": key}
                )

    modes = []
    for mode_data in modes_dict.values():
        tasks = []
        for task_data in mode_data["tasks"].values():
            tasks.append({
                "value": task_data["value"],
                "agents": task_data["agents"],
            })
        modes.append({
            "value": mode_data["value"],
            "tasks": tasks,
        })

    return {"modes": modes}


def _get_yaml_path(
    mode_name: str,
    task_name: str,
    agent_name: str | None = None,
) -> Path:
    """
    根据 mode, task, agent 获取对应的 YAML 文件路径。
    """
    if agent_name:
        return PROMPTS_DIR / mode_name / task_name / f"{agent_name}.yaml"
    return PROMPTS_DIR / mode_name / f"{task_name}.yaml"


_PRIMARY_AGENT_DEFAULT_CONTENT = """# 主智能体默认提示词
entries:
  - name: system_prompt
    role: system
    content: |
      你是一个主智能体，负责协调和调度子智能体完成复杂任务。请根据任务需求规划并委派工作。
    order_index: 0
    is_enabled: true
    token_count: 0
  - name: user_prompt
    role: user
    content: |
      请开始执行任务。
    order_index: 1
    is_enabled: true
    token_count: 0
"""

_SUBAGENT_DEFAULT_CONTENT = """# 子智能体默认提示词
entries:
  - name: system_prompt
    role: system
    content: |
      你是一个子智能体，负责执行主智能体委派的具体任务。请专注于完成当前分配的工作。
    order_index: 0
    is_enabled: true
    token_count: 0
  - name: user_prompt
    role: user
    content: |
      请开始执行任务。
    order_index: 1
    is_enabled: true
    token_count: 0
"""


def create_custom_agent_prompt_yaml(
    mode_name: str,
    task_name: str,
    agent_name: str,
    kind: str = "subagent",
    content: str | None = None,
) -> Path:
    """
    创建自定义智能体的默认提示词 YAML 文件。

    Args:
        mode_name: 模式名称（通常为 "assistant"）。
        task_name: 任务名称（通常为 "agent"）。
        agent_name: 智能体标识。
        kind: 智能体类型 "primary" 或 "subagent"，影响默认模板。
        content: 可选的 YAML 内容，默认使用模板。

    Returns:
        创建的 YAML 文件路径。
    """
    task_dir = PROMPTS_DIR / mode_name / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    yaml_path = task_dir / f"{agent_name}.yaml"
    if content:
        yaml_content = content
    elif kind == "primary":
        yaml_content = _PRIMARY_AGENT_DEFAULT_CONTENT
    else:
        yaml_content = _SUBAGENT_DEFAULT_CONTENT
    yaml_path.write_text(yaml_content, encoding="utf-8")
    logger.info(f"已创建自定义智能体提示词 YAML: {yaml_path}")
    return yaml_path


def delete_custom_agent_prompt_yaml(
    mode_name: str,
    task_name: str,
    agent_name: str,
) -> bool:
    """
    删除自定义智能体的提示词 YAML 文件。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: 智能体标识。

    Returns:
        是否成功删除。
    """
    yaml_path = _get_yaml_path(mode_name, task_name, agent_name)
    if not yaml_path.exists():
        logger.warning(f"提示词 YAML 不存在，无需删除: {yaml_path}")
        return False

    yaml_path.unlink()
    logger.info(f"已删除自定义智能体提示词 YAML: {yaml_path}")
    return True


def reset_custom_agent_prompt_yaml(
    mode_name: str,
    task_name: str,
    agent_name: str,
) -> Path:
    """
    重置自定义智能体的提示词 YAML 为默认模板。

    先删除再创建。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: 智能体标识。

    Returns:
        创建的 YAML 文件路径。
    """
    delete_custom_agent_prompt_yaml(mode_name, task_name, agent_name)
    return create_custom_agent_prompt_yaml(mode_name, task_name, agent_name)
