/**
 * Macro Lexer - 宏词法分析器
 *
 * 负责识别文本中的宏表达式和解析宏参数。
 */

import type { MacroMatch, MacroToken, TokenType } from "./types";

const MACRO_PATTERN = /\{\{([^{}]+)\}\}/g;
const SEPARATOR = "::";

/**
 * 在文本中查找所有宏表达式
 */
export function findMacros(text: string): MacroMatch[] {
  const matches: MacroMatch[] = [];
  let match: RegExpExecArray | null;

  MACRO_PATTERN.lastIndex = 0;

  while ((match = MACRO_PATTERN.exec(text)) !== null) {
    const body = match[1].trim();
    if (body && !body.includes("\n")) {
      matches.push({
        body,
        raw: match[0],
        start: match.index,
        end: match.index + match[0].length,
      });
    }
  }

  return matches;
}

/**
 * 将参数字符串解析为 Token 列表
 */
export function tokenizeArgs(argsStr: string): MacroToken[] {
  if (!argsStr) return [];

  const parts = splitArgs(argsStr);
  return parts.map(parseToken);
}

/**
 * 按 :: 分隔参数，但需考虑字符串内的 ::
 */
function splitArgs(argsStr: string): string[] {
  const parts: string[] = [];
  let current = "";
  let inString = false;

  for (let i = 0; i < argsStr.length; i++) {
    const char = argsStr[i];

    if (char === '"' && (i === 0 || argsStr[i - 1] !== "\\")) {
      inString = !inString;
      current += char;
    } else if (!inString && argsStr.slice(i, i + 2) === SEPARATOR) {
      if (current.trim()) {
        parts.push(current.trim());
      }
      current = "";
      i++;
    } else {
      current += char;
    }
  }

  if (current.trim()) {
    parts.push(current.trim());
  }

  return parts;
}

/**
 * 解析单个参数为 Token
 */
function parseToken(part: string): MacroToken {
  part = part.trim();

  if (part.startsWith('"') && part.endsWith('"')) {
    return parseString(part);
  }

  if (part.startsWith("list(") && part.endsWith(")")) {
    return parseList(part);
  }

  if (part === "true" || part === "false") {
    return parseBoolean(part);
  }

  if (part.includes("-") && !part.startsWith("-")) {
    const rangePart = parseRange(part);
    if (rangePart) return rangePart;
  }

  if (isNumber(part)) {
    return parseNumber(part);
  }

  if (isIdentifier(part)) {
    return { type: "identifier" as TokenType, value: part, raw: part };
  }

  throw new Error(`无法解析参数: ${part}`);
}

function parseBoolean(part: string): MacroToken {
  const value = part === "true";
  return { type: "boolean" as TokenType, value, raw: part };
}

function parseString(part: string): MacroToken {
  const content = part.slice(1, -1);
  const unescaped = content.replace(/\\"/g, '"');
  return { type: "string" as TokenType, value: unescaped, raw: part };
}

function parseList(part: string): MacroToken {
  const content = part.slice(5, -1);
  if (!content) {
    throw new Error("列表不能为空");
  }

  const items = content.split(",").map((item) => item.trim());
  if (items.some((item) => !item)) {
    throw new Error("列表项不能为空");
  }

  return { type: "list" as TokenType, value: items, raw: part };
}

function parseRange(part: string): MacroToken | null {
  const dashIndex = part.indexOf("-");
  if (dashIndex <= 0) return null;

  const lowerStr = part.slice(0, dashIndex);
  const upperStr = part.slice(dashIndex + 1);

  const lower = parseInt(lowerStr, 10);
  const upper = parseInt(upperStr, 10);

  if (isNaN(lower) || isNaN(upper)) return null;
  if (lower >= upper) {
    throw new Error(`范围下界必须小于上界: ${part}`);
  }

  return { type: "range" as TokenType, value: [lower, upper], raw: part };
}

function parseNumber(part: string): MacroToken {
  const value = parseInt(part, 10);
  if (isNaN(value)) {
    throw new Error(`无效的数值: ${part}`);
  }
  return { type: "number" as TokenType, value, raw: part };
}

function isNumber(part: string): boolean {
  if (part.startsWith("-")) {
    return part.length > 1 && /^\d+$/.test(part.slice(1));
  }
  return /^\d+$/.test(part);
}

function isIdentifier(part: string): boolean {
  if (!part) return false;
  return /^[a-z][a-z0-9_]*$/.test(part);
}
