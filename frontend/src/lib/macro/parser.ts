/**
 * Macro Parser - 宏语法解析器
 *
 * 负责将宏体解析为 AST 节点。
 */

import { findMacros, tokenizeArgs } from "./lexer";
import { isValidMacro } from "./registry";
import type { MacroMatch, MacroNode } from "./types";

const NO_ARG_MACROS = new Set(["getlist", "getworld", "endif"]);

export class MacroParseError extends Error {
  raw: string;

  constructor(message: string, raw: string) {
    super(message);
    this.name = "MacroParseError";
    this.raw = raw;
  }
}

/**
 * 解析宏匹配为 AST 节点
 */
export function parseMacro(match: MacroMatch): MacroNode {
  const { body } = match;

  const separatorIndex = body.indexOf("::");
  const name = separatorIndex >= 0 ? body.slice(0, separatorIndex).trim() : body.trim();

  if (!name) {
    throw new MacroParseError("宏名不能为空", match.raw);
  }

  if (!isValidMacro(name)) {
    throw new MacroParseError(`未知的宏名: ${name}`, match.raw);
  }

  const argsStr = separatorIndex >= 0 ? body.slice(separatorIndex + 2) : "";

  let args;
  try {
    args = tokenizeArgs(argsStr);
  } catch (e) {
    throw new MacroParseError(
      e instanceof Error ? e.message : String(e),
      match.raw
    );
  }

  if (NO_ARG_MACROS.has(name)) {
    if (args.length !== 0) {
      throw new MacroParseError(
        `${name} 宏不接受参数，收到: ${args.length}`,
        match.raw
      );
    }
  }

  return {
    name,
    args,
    raw: match.raw,
    start: match.start,
    end: match.end,
  };
}

/**
 * 解析文本中所有有效的宏
 */
export function parseAllMacros(text: string): MacroNode[] {
  const matches = findMacros(text);
  const nodes: MacroNode[] = [];

  for (const match of matches) {
    try {
      const node = parseMacro(match);
      nodes.push(node);
    } catch {
      // 解析失败的宏跳过
    }
  }

  return nodes;
}

/**
 * 尝试解析宏匹配，失败返回 null
 */
export function tryParseMacro(match: MacroMatch): MacroNode | null {
  try {
    return parseMacro(match);
  } catch {
    return null;
  }
}
