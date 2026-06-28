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
  name: string;
  description: string;
  isReadonly: boolean;
}

/** 设置数据 */
export interface Settings {
  language: LanguageCode;
  theme: ThemeMode;
  fontFamily: string;
  codeFontFamily: string;
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
}

/** 设置响应（后端格式） */
export interface SettingsResponse {
  language: string;
  theme: string;
  font_family: string;
  code_font_family?: string;
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
}

/** 设置更新请求 */
export interface SettingsUpdateRequest {
  language?: string;
  theme?: string;
  font_family?: string;
  code_font_family?: string;
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
}

/** 字体选项 */
export interface FontOption {
  value: string;
  label: string;
}

export const DEFAULT_FONT_FAMILY = "SourceHanSerifCN-VF";
export const DEFAULT_CODE_FONT_FAMILY = "JetBrainsMapleMono";

/** 可用字体列表 */
export const FONT_OPTIONS: FontOption[] = [
  { value: "SourceHanSerifCN-VF", label: "思源宋体" },
  { value: "SourceHanSansCN-VF", label: "思源黑体" },
  { value: "ChillKai", label: "寒蝉手札体" },
];

/** 代码字体选项 */
export const CODE_FONT_OPTIONS: FontOption[] = [
  { value: DEFAULT_CODE_FONT_FAMILY, label: "JetBrains Maple Mono" },
];

export function getSupportedFontFamily(fontFamily: string): string {
  if (FONT_OPTIONS.some((option) => option.value === fontFamily)) return fontFamily;
  return DEFAULT_FONT_FAMILY;
}

export function getSupportedCodeFontFamily(codeFontFamily: string): string {
  if (CODE_FONT_OPTIONS.some((option) => option.value === codeFontFamily)) return codeFontFamily;
  return DEFAULT_CODE_FONT_FAMILY;
}
