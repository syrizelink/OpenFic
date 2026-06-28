/**
 * Macro Module - 宏解析模块
 *
 * 提供提示词链中宏表达式的解析和验证功能。
 */

export type {
  TokenType,
  MacroToken,
  MacroNode,
  MacroMatch,
  MacroMeta,
} from "./types";

export { findMacros, tokenizeArgs } from "./lexer";

export {
  parseMacro,
  parseAllMacros,
  tryParseMacro,
  MacroParseError,
} from "./parser";

export {
  MACRO_REGISTRY,
  getMacroNames,
  isValidMacro,
  isConfigurable,
  getMacroMeta,
} from "./registry";

export {
  getMacroCompletions,
  findUncompletedMacro,
} from "./completions";
export type { CompletionResult } from "./completions";

