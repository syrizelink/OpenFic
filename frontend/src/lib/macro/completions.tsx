/**
 * Macro Completions - 宏补全数据源
 *
 * 根据当前输入上下文提供补全建议。
 */

import { BookOpen, Database, GitBranch } from "lucide-react";

import type { AutocompleteItem } from "@/components";

import { MACRO_REGISTRY } from "./registry";

/** 宏名到图标的映射 */
const MACRO_ICONS: Record<string, React.ReactNode> = {
  getmem: <Database size={14} />,
  getlist: <BookOpen size={14} />,
  getworld: <BookOpen size={14} />,
  if: <GitBranch size={14} />,
  endif: <GitBranch size={14} />,
};

const NO_ARG_MACROS = new Set(["getlist", "getworld", "endif"]);

/** 补全结果 */
export interface CompletionResult {
  /** 补全项列表 */
  items: AutocompleteItem[];
  /** 无固定项时的提示 */
  hint?: string;
}

/**
 * 解析当前输入上下文
 *
 * 返回格式：
 * - macroName: 已输入的宏名（可能为空或部分输入）
 * - args: 已输入的参数列表
 * - isComplete: 宏名是否已完整（后面有 ::）
 * - currentArgPartial: 当前正在输入的参数（部分）
 */
interface ParsedContext {
  macroName: string;
  args: string[];
  isComplete: boolean;
  currentArgPartial: string;
}

function parseContext(textAfterBraces: string): ParsedContext {
  const parts = textAfterBraces.split("::");

  if (parts.length === 1) {
    // 只有宏名（可能是部分）
    return {
      macroName: parts[0],
      args: [],
      isComplete: false,
      currentArgPartial: parts[0],
    };
  }

  // 有 :: 分隔符，宏名已完整
  const macroName = parts[0];
  const argParts = parts.slice(1);

  // 最后一个 part 可能是正在输入的参数
  const currentArgPartial = argParts[argParts.length - 1] || "";
  const completedArgs = argParts.slice(0, -1);

  return {
    macroName,
    args: completedArgs,
    isComplete: true,
    currentArgPartial,
  };
}

/**
 * 获取一级补全（宏名）
 */
function getMacroNameCompletions(partial: string): AutocompleteItem[] {
  const items: AutocompleteItem[] = [];

  for (const [name, meta] of Object.entries(MACRO_REGISTRY)) {
    // 过滤匹配的宏名
    if (partial && !name.toLowerCase().startsWith(partial.toLowerCase())) {
      continue;
    }

    items.push({
      label: name,
      insertText: NO_ARG_MACROS.has(name) ? `${name}}}` : `${name}::`,
      description: meta.description,
      icon: MACRO_ICONS[name],
    });
  }

  return items;
}

/**
 * 获取 getmem 宏的参数补全
 */
function getGetmemArgCompletions(
  argIndex: number,
  partial: string,
  args: string[],
): CompletionResult {
  if (argIndex === 0) {
    // 一级：chapter
    const items: AutocompleteItem[] = [];

    if (!partial || "chapter".startsWith(partial.toLowerCase())) {
      items.push({
        label: "chapter",
        insertText: "chapter::",
        description: "章节记忆",
      });
    }

    return { items };
  }

  if (argIndex === 1 && args[0] === "chapter") {
    // 二级：latest/near/middle/far
    const fields = [
      { name: "latest", desc: "最新章节原文" },
      { name: "near", desc: "最新9章原文" },
      { name: "middle", desc: "最新10个章节摘要" },
      { name: "far", desc: "全部远期摘要" },
    ];

    const items: AutocompleteItem[] = fields
      .filter((f) => !partial || f.name.startsWith(partial.toLowerCase()))
      .map((f) => ({
        label: f.name,
        insertText: `${f.name}}}`,
        description: f.desc,
      }));

    return { items };
  }

  return { items: [] };
}

/**
 * 获取 if 宏的参数补全
 */
function getIfArgCompletions(argIndex: number): CompletionResult {
  if (argIndex === 0) {
    return {
      items: [],
      hint: "输入bool类型的变量名",
    };
  }

  return { items: [] };
}

/**
 * 根据当前上下文获取补全建议
 *
 * @param textAfterBraces - {{ 之后的文本（不包含 {{）
 */
export function getMacroCompletions(textAfterBraces: string): CompletionResult {
  const ctx = parseContext(textAfterBraces);

  // 如果宏名未完成，显示宏名补全
  if (!ctx.isComplete) {
    return {
      items: getMacroNameCompletions(ctx.currentArgPartial),
    };
  }

  // 宏名已完成，根据宏类型和参数位置提供补全
  const argIndex = ctx.args.length; // 当前正在输入的参数索引

  switch (ctx.macroName) {
    case "getmem":
      return getGetmemArgCompletions(argIndex, ctx.currentArgPartial, ctx.args);

    case "getlist":
    case "getworld":
      return { items: [] };

    case "if":
      return getIfArgCompletions(argIndex);

    case "endif":
      return { items: [] };

    default:
      return { items: [] };
  }
}

/**
 * 检查文本中是否有未闭合的宏起始符
 *
 * @returns {{ 之后的文本，如果没有未闭合的宏则返回 null
 */
export function findUncompletedMacro(textBefore: string): string | null {
  // 查找最后一个 {{ 且后面没有 }}
  const lastOpen = textBefore.lastIndexOf("{{");
  if (lastOpen === -1) return null;

  const afterOpen = textBefore.slice(lastOpen + 2);

  // 检查是否已经闭合
  if (afterOpen.includes("}}")) return null;

  // 不允许换行
  if (afterOpen.includes("\n")) return null;

  return afterOpen;
}
