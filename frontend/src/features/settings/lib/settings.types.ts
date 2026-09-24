/**
 * Settings Types
 *
 * 设置相关类型定义。
 */

import type { IndexAutoStrategy, IndexMode } from "@/lib/index-status";
import type { ThemeConfig, ThemeConfigResponse, ThemeMode, ThemePresetId } from "@/lib/theme";

export type { ThemeMode } from "@/lib/theme";

/** 支持的语言代码 */
export type LanguageCode = "zh-CN" | "en";

export type AgentToolPermissionMode = "allow" | "ask" | "deny";

export interface AgentToolPermission {
  toolName: string;
  mode: AgentToolPermissionMode;
}

export interface AgentToolMetadata {
  key: string;
  isReadonly: boolean;
}

/** 设置数据 */
export interface Settings {
  language: LanguageCode;
  theme: ThemeMode;
  themePreset: ThemePresetId;
  lightThemePreset: ThemePresetId;
  darkThemePreset: ThemePresetId;
  themeConfig: ThemeConfig;
  fontFamily: string;
  codeFontFamily: string;
  baseFontSize: number;
  editorFontSize: number;
  defaultModel: string;
  lightModel: string;
  summaryModel: string;
  summaryAutoGenerateChapter: boolean;
  summaryAutoGenerateLongTerm: boolean;
  summaryMinChapterWordCount: number;
  summaryBatchSize: number;
  summaryLongTermInterval: number;
  summaryChapterTargetLength: number;
  summaryLongTermTargetLength: number;
  defaultEmbeddingModel: string;
  indexMode: IndexMode;
  indexEnabledProjects: string[];
  indexChunkSize: number;
  indexChunkOverlap: number;
  indexAutoStrategy: IndexAutoStrategy;
  indexRerankEnabled: boolean;
  defaultRerankModel: string;
  agentBypassToolApproval: boolean;
  agentToolPermissions: AgentToolPermission[];
  auditPersistDetails: boolean;
  compressSystemPrompts: boolean;
  autoCompactContext: boolean;
  compactionModel: string;
  compactionTriggerRatio: number;
  compactionTailTokenBudget: number;
  compactionTailWindowRatio: number;
  compactionMinCompactableTokens: number;
  autoPruneToolOutputs: boolean;
  pruneProtectedTokens: number;
  pruneMinimumTokens: number;
  telemetryEnabled: boolean;
  editorAutoIndent: boolean;
  editorAutoConvertPunctuation: boolean;
  editorAutoPairSymbols: boolean;
  editorShowLineNumbers: boolean;
}

/** 设置响应（后端格式） */
export interface SettingsResponse {
  language: string;
  theme: string;
  theme_preset?: string;
  light_theme_preset?: string;
  dark_theme_preset?: string;
  theme_config?: ThemeConfigResponse;
  font_family: string;
  code_font_family?: string;
  base_font_size?: number;
  editor_font_size?: number;
  default_model: string;
  light_model: string;
  summary_model: string;
  summary_auto_generate_chapter: boolean;
  summary_auto_generate_long_term: boolean;
  summary_min_chapter_word_count: number;
  summary_batch_size: number;
  summary_long_term_interval: number;
  summary_chapter_target_length: number;
  summary_long_term_target_length: number;
  default_embedding_model: string;
  index_mode: IndexMode;
  index_enabled_projects: string[];
  index_chunk_size: number;
  index_chunk_overlap: number;
  index_auto_strategy: IndexAutoStrategy;
  index_rerank_enabled: boolean;
  default_rerank_model: string;
  agent_bypass_tool_approval: boolean;
  agent_tool_permissions: Array<{
    tool_name: string;
    mode: AgentToolPermissionMode;
  }>;
  audit_persist_details: boolean;
  compress_system_prompts: boolean;
  auto_compact_context: boolean;
  compaction_model: string;
  compaction_trigger_ratio: number;
  compaction_tail_token_budget: number;
  compaction_tail_window_ratio: number;
  compaction_min_compactable_tokens: number;
  auto_prune_tool_outputs: boolean;
  prune_protected_tokens: number;
  prune_minimum_tokens: number;
  telemetry_enabled: boolean;
  editor_auto_indent?: boolean;
  editor_auto_convert_punctuation?: boolean;
  editor_auto_pair_symbols?: boolean;
  editor_show_line_numbers?: boolean;
}

/** 设置更新请求 */
export interface SettingsUpdateRequest {
  language?: string;
  theme?: string;
  theme_preset?: string;
  light_theme_preset?: string;
  dark_theme_preset?: string;
  theme_config?: ThemeConfigResponse;
  font_family?: string;
  code_font_family?: string;
  base_font_size?: number;
  editor_font_size?: number;
  default_model?: string;
  light_model?: string;
  summary_model?: string;
  summary_auto_generate_chapter?: boolean;
  summary_auto_generate_long_term?: boolean;
  summary_min_chapter_word_count?: number;
  summary_batch_size?: number;
  summary_long_term_interval?: number;
  summary_chapter_target_length?: number;
  summary_long_term_target_length?: number;
  confirm_summary_range_invalidation?: boolean;
  default_embedding_model?: string;
  index_mode?: IndexMode;
  index_enabled_projects?: string[];
  index_chunk_size?: number;
  index_chunk_overlap?: number;
  index_auto_strategy?: IndexAutoStrategy;
  index_rerank_enabled?: boolean;
  default_rerank_model?: string;
  agent_bypass_tool_approval?: boolean;
  agent_tool_permissions?: Array<{
    tool_name: string;
    mode: AgentToolPermissionMode;
  }>;
  audit_persist_details?: boolean;
  compress_system_prompts?: boolean;
  auto_compact_context?: boolean;
  compaction_model?: string;
  compaction_trigger_ratio?: number;
  compaction_tail_token_budget?: number;
  compaction_tail_window_ratio?: number;
  compaction_min_compactable_tokens?: number;
  auto_prune_tool_outputs?: boolean;
  prune_protected_tokens?: number;
  prune_minimum_tokens?: number;
  telemetry_enabled?: boolean;
  editor_auto_indent?: boolean;
  editor_auto_convert_punctuation?: boolean;
  editor_auto_pair_symbols?: boolean;
  editor_show_line_numbers?: boolean;
}

export interface AuditDetailsStorage {
  detailRecordsCount: number;
  detailBytes: number;
}

/** 字体选项 */
export interface FontOption {
  value: string;
  label: string;
  fontFamily: string;
}

export interface FontDefinition {
  value: string;
  labelKey: string;
}

export const DEFAULT_FONT_FAMILY = "Noto Serif SC Variable";
export const DEFAULT_CODE_FONT_FAMILY = "JetBrains Mono Variable";
export const SYSTEM_FONT_FAMILY = "system-ui";
export const SYSTEM_CODE_FONT_FAMILY = "ui-monospace";

/** 可用字体列表 */
export const FONT_OPTIONS: FontDefinition[] = [
  { value: SYSTEM_FONT_FAMILY, labelKey: "settings.fontOptionSystemDefault" },
  { value: "Noto Serif SC Variable", labelKey: "settings.fontOptionNotoSerifSC" },
  { value: "Noto Sans SC Variable", labelKey: "settings.fontOptionNotoSansSC" },
  { value: "ZCOOL KuaiLe", labelKey: "settings.fontOptionZcoolKuaiLe" },
  { value: "ZCOOL XiaoWei", labelKey: "settings.fontOptionZcoolXiaoWei" },
  { value: "Ma Shan Zheng", labelKey: "settings.fontOptionMaShanZheng" },
  { value: "WDXL Lubrifont SC", labelKey: "settings.fontOptionWdXlLubrifontSc" },
];

/** 代码字体选项 */
export const CODE_FONT_OPTIONS: FontDefinition[] = [
  { value: SYSTEM_CODE_FONT_FAMILY, labelKey: "settings.fontOptionSystemDefault" },
  { value: "JetBrains Mono Variable", labelKey: "settings.fontOptionJetBrainsMono" },
  { value: "Fira Code Variable", labelKey: "settings.fontOptionFiraCode" },
  { value: "Roboto Mono Variable", labelKey: "settings.fontOptionRobotoMono" },
  { value: "Source Code Pro Variable", labelKey: "settings.fontOptionSourceCodePro" },
  { value: "Cascadia Code Variable", labelKey: "settings.fontOptionCascadiaCode" },
];

export function getFontOptions(t: (key: string) => string): FontOption[] {
  return FONT_OPTIONS.map((option) => ({
    value: option.value,
    label: t(option.labelKey),
    fontFamily: option.value,
  }));
}

export function getCodeFontOptions(t: (key: string) => string): FontOption[] {
  return CODE_FONT_OPTIONS.map((option) => ({
    value: option.value,
    label: t(option.labelKey),
    fontFamily: option.value,
  }));
}

export function getSupportedFontFamily(fontFamily: string): string {
  if (FONT_OPTIONS.some((option) => option.value === fontFamily)) return fontFamily;
  return DEFAULT_FONT_FAMILY;
}

export function getSupportedCodeFontFamily(codeFontFamily: string): string {
  if (CODE_FONT_OPTIONS.some((option) => option.value === codeFontFamily)) return codeFontFamily;
  return DEFAULT_CODE_FONT_FAMILY;
}
