/**
 * Macro Types - 宏类型定义
 */

/** Token 类型 */
export type TokenType = "identifier" | "number" | "range" | "string" | "list" | "boolean";

/** 宏参数 Token */
export interface MacroToken {
  type: TokenType;
  value: string | number | boolean | [number, number] | string[];
  raw: string;
}

/** 宏 AST 节点 */
export interface MacroNode {
  name: string;
  args: MacroToken[];
  raw: string;
  start: number;
  end: number;
}

/** 宏匹配结果 */
export interface MacroMatch {
  body: string;
  raw: string;
  start: number;
  end: number;
}

/** 宏元信息 */
export interface MacroMeta {
  name: string;
  configurable: boolean;
  description: string;
}
