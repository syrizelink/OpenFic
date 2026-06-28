# -*- coding: utf-8 -*-
"""
Macro Registry - 宏注册表。

定义预定义的宏名集合和元信息。
"""

from dataclasses import dataclass


@dataclass
class MacroMeta:
    """
    宏元信息。

    Attributes:
        name: 宏名。
        configurable: 是否可在侧边栏配置。
        description: 描述。
        handler_class: 处理器类名（延迟加载）。
    """

    name: str
    configurable: bool
    description: str
    handler_class: str


MACRO_REGISTRY: dict[str, MacroMeta] = {
    "getmem": MacroMeta(
        name="getmem",
        configurable=False,
        description="获取章节记忆内容",
        handler_class="GetMemHandler",
    ),
    "getlist": MacroMeta(
        name="getlist",
        configurable=False,
        description="获取最新 50 个章节的目录列表",
        handler_class="GetListHandler",
    ),
    "getworld": MacroMeta(
        name="getworld",
        configurable=False,
        description="获取当前项目世界书常驻和关键词命中条目",
        handler_class="GetWorldHandler",
    ),
    "if": MacroMeta(
        name="if",
        configurable=True,
        description="条件渲染块开始（基于bool变量）",
        handler_class="IfHandler",
    ),
    "endif": MacroMeta(
        name="endif",
        configurable=True,
        description="条件渲染块结束",
        handler_class="EndIfHandler",
    ),
}


def get_macro_names() -> set[str]:
    """获取所有预定义宏名。"""
    return set(MACRO_REGISTRY.keys())


def is_valid_macro(name: str) -> bool:
    """检查宏名是否有效。"""
    return name in MACRO_REGISTRY


def is_configurable(name: str) -> bool:
    """检查宏是否可配置。"""
    meta = MACRO_REGISTRY.get(name)
    return meta.configurable if meta else False
