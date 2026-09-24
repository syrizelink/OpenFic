/**
 * Settings API
 *
 * 设置 API 客户端。
 */

import { apiClient } from "@/lib/api-client";
import { normalizeThemeMode, normalizeThemePreset, transformThemeConfig } from "@/lib/theme";

import { SYSTEM_LIGHT_MODEL_REFERENCE } from "./agent-definitions.types";
import type {
  AgentToolMetadata,
  AuditDetailsStorage,
  Settings,
  SettingsResponse,
  SettingsUpdateRequest,
} from "./settings.types";
import {
  DEFAULT_CODE_FONT_FAMILY,
  getSupportedCodeFontFamily,
  getSupportedFontFamily,
} from "./settings.types";

/**
 * 后端响应字段转换（snake_case -> camelCase）
 */
export function transformSettings(raw: SettingsResponse): Settings {
  const theme = normalizeThemeMode(raw.theme);
  const appearance = theme === "dark" ? "dark" : "light";
  const themePreset = normalizeThemePreset(raw.theme_preset, appearance);
  const lightThemePreset = normalizeThemePreset(raw.light_theme_preset ?? themePreset, "light");
  const darkThemePreset = normalizeThemePreset(raw.dark_theme_preset ?? themePreset, "dark");

  return {
    language: raw.language as Settings["language"],
    theme,
    themePreset: appearance === "dark" ? darkThemePreset : lightThemePreset,
    lightThemePreset,
    darkThemePreset,
    themeConfig: transformThemeConfig(raw.theme_config),
    fontFamily: getSupportedFontFamily(raw.font_family),
    codeFontFamily: getSupportedCodeFontFamily(raw.code_font_family || DEFAULT_CODE_FONT_FAMILY),
    baseFontSize: raw.base_font_size ?? 14,
    editorFontSize: raw.editor_font_size ?? 16,
    defaultModel: raw.default_model || "",
    lightModel: raw.light_model || "",
    summaryModel: raw.summary_model || SYSTEM_LIGHT_MODEL_REFERENCE,
    summaryAutoGenerateChapter: raw.summary_auto_generate_chapter ?? true,
    summaryAutoGenerateLongTerm: raw.summary_auto_generate_long_term ?? true,
    summaryMinChapterWordCount: raw.summary_min_chapter_word_count ?? 500,
    summaryBatchSize: raw.summary_batch_size ?? 10,
    summaryLongTermInterval: raw.summary_long_term_interval ?? 10,
    summaryChapterTargetLength: raw.summary_chapter_target_length ?? 200,
    summaryLongTermTargetLength: raw.summary_long_term_target_length ?? 500,
    defaultEmbeddingModel: raw.default_embedding_model || "",
    indexMode: raw.index_mode ?? "off",
    indexEnabledProjects: raw.index_enabled_projects ?? [],
    indexChunkSize: raw.index_chunk_size ?? 800,
    indexChunkOverlap: raw.index_chunk_overlap ?? 100,
    indexAutoStrategy: raw.index_auto_strategy ?? "off",
    indexRerankEnabled: raw.index_rerank_enabled ?? false,
    defaultRerankModel: raw.default_rerank_model || "",
    agentBypassToolApproval: raw.agent_bypass_tool_approval ?? false,
    agentToolPermissions: (raw.agent_tool_permissions || []).map((item) => ({
      toolName: item.tool_name,
      mode: item.mode,
    })),
    auditPersistDetails: raw.audit_persist_details ?? false,
    compressSystemPrompts: raw.compress_system_prompts ?? false,
    autoCompactContext: raw.auto_compact_context ?? true,
    compactionModel: raw.compaction_model || "__session_model__",
    compactionTriggerRatio: raw.compaction_trigger_ratio ?? 0.8,
    compactionTailTokenBudget: raw.compaction_tail_token_budget ?? 20000,
    compactionTailWindowRatio: raw.compaction_tail_window_ratio ?? 0.5,
    compactionMinCompactableTokens: raw.compaction_min_compactable_tokens ?? 2000,
    autoPruneToolOutputs: raw.auto_prune_tool_outputs ?? false,
    pruneProtectedTokens: raw.prune_protected_tokens ?? 100000,
    pruneMinimumTokens: raw.prune_minimum_tokens ?? 20000,
    telemetryEnabled: raw.telemetry_enabled ?? true,
    editorAutoIndent: raw.editor_auto_indent ?? true,
    editorAutoConvertPunctuation: raw.editor_auto_convert_punctuation ?? false,
    editorAutoPairSymbols: raw.editor_auto_pair_symbols ?? false,
    editorShowLineNumbers: raw.editor_show_line_numbers ?? false,
  };
}

/**
 * 获取设置
 */
export async function fetchSettings(): Promise<Settings> {
  const response = await apiClient.get<SettingsResponse>("/settings");
  return transformSettings(response.data);
}

/**
 * 更新设置
 */
export async function updateSettings(data: SettingsUpdateRequest): Promise<Settings> {
  const response = await apiClient.put<SettingsResponse>("/settings", data);
  return transformSettings(response.data);
}

export async function fetchAgentTools(): Promise<AgentToolMetadata[]> {
  const response = await apiClient.get<
    Array<{
      key: string;
      is_readonly: boolean;
    }>
  >("/agent/tools");
  return response.data.map((tool) => ({
    key: tool.key,
    isReadonly: tool.is_readonly,
  }));
}

export async function fetchAuditDetailsStorage(): Promise<AuditDetailsStorage> {
  const response = await apiClient.get<{
    detail_records_count: number;
    detail_bytes: number;
  }>("/settings/audit-details/storage");
  return {
    detailRecordsCount: response.data.detail_records_count,
    detailBytes: response.data.detail_bytes,
  };
}

export async function clearAuditDetails(): Promise<void> {
  await apiClient.delete("/settings/audit-details");
}
