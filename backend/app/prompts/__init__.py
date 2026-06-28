# -*- coding: utf-8 -*-
"""
Prompts - 默认提示词配置模块。

该模块从 YAML 文件加载默认提示词配置，用于：
1. 提供提示词链的元数据（mode > task > agent 结构）
2. 在用户重置提示词链时恢复默认内容
3. 管理自定义智能体的默认提示词 YAML 文件
"""

from app.prompts.loader import (
    create_custom_agent_prompt_yaml,
    delete_custom_agent_prompt_yaml,
    get_prompt_chains_metadata,
    load_prompt_chain,
    reset_custom_agent_prompt_yaml,
)

__all__ = [
    "create_custom_agent_prompt_yaml",
    "delete_custom_agent_prompt_yaml",
    "get_prompt_chains_metadata",
    "load_prompt_chain",
    "reset_custom_agent_prompt_yaml",
]