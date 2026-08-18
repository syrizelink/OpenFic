/**
 * Settings Types
 *
 * 设置相关类型定义。
 */

import type { IndexAutoStrategy, IndexMode } from "@/lib/index-status";

/** 支持的语言代码 */
export type LanguageCode = "zh-CN" | "en";

/** 支持的主题 */
export type ThemeMode = "light" | "dark";

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
  fontFamily: string;
  codeFontFamily: string;
  baseFontSize: number;
  editorFontSize: number;
  defaultModel: string;
  lightModel: string;
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
  telemetryEnabled: boolean;
  editorAutoIndent: boolean;
  editorAutoConvertPunctuation: boolean;
  editorAutoPairSymbols: boolean;
}

/** 设置响应（后端格式） */
export interface SettingsResponse {
  language: string;
  theme: string;
  font_family: string;
  code_font_family?: string;
  base_font_size?: number;
  editor_font_size?: number;
  default_model: string;
  light_model: string;
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
  telemetry_enabled: boolean;
  editor_auto_indent?: boolean;
  editor_auto_convert_punctuation?: boolean;
  editor_auto_pair_symbols?: boolean;
}

/** 设置更新请求 */
export interface SettingsUpdateRequest {
  language?: string;
  theme?: string;
  font_family?: string;
  code_font_family?: string;
  base_font_size?: number;
  editor_font_size?: number;
  default_model?: string;
  light_model?: string;
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
  telemetry_enabled?: boolean;
  editor_auto_indent?: boolean;
  editor_auto_convert_punctuation?: boolean;
  editor_auto_pair_symbols?: boolean;
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
