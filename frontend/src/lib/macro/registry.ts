/**
 * Macro Registry - 宏注册表
 *
 * 定义预定义的宏名集合和元信息。
 */

import type { MacroMeta } from "./types";

export const MACRO_REGISTRY: Record<string, MacroMeta> = {
  getmem: {
    name: "getmem",
    configurable: false,
    description: "获取章节记忆内容",
  },
  getlist: {
    name: "getlist",
    configurable: false,
    description: "获取最新 50 个章节的目录列表",
  },
  getworld: {
    name: "getworld",
    configurable: false,
    description: "获取当前项目世界书常驻和关键词命中条目",
  },
  if: {
    name: "if",
    configurable: true,
    description: "条件渲染块开始（基于bool变量）",
  },
  endif: {
    name: "endif",
    configurable: true,
    description: "条件渲染块结束",
  },
};

/** 获取所有预定义宏名 */
export function getMacroNames(): Set<string> {
  return new Set(Object.keys(MACRO_REGISTRY));
}

/** 检查宏名是否有效 */
export function isValidMacro(name: string): boolean {
  return name in MACRO_REGISTRY;
}

/** 检查宏是否可配置 */
export function isConfigurable(name: string): boolean {
  const meta = MACRO_REGISTRY[name];
  return meta?.configurable ?? false;
}

/** 获取宏元信息 */
export function getMacroMeta(name: string): MacroMeta | undefined {
  return MACRO_REGISTRY[name];
}
