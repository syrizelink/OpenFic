/**
 * Settings API
 *
 * 设置 API 客户端。
 */

import { apiClient } from "@/lib/api-client";
import type {
  AgentToolMetadata,
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
  return {
    language: raw.language as Settings["language"],
    theme: raw.theme as Settings["theme"],
    fontFamily: getSupportedFontFamily(raw.font_family),
    codeFontFamily: getSupportedCodeFontFamily(
      raw.code_font_family || DEFAULT_CODE_FONT_FAMILY
    ),
    defaultModel: raw.default_model || "",
    lightModel: raw.light_model || "",
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
export async function updateSettings(
  data: SettingsUpdateRequest
): Promise<Settings> {
  const response = await apiClient.put<SettingsResponse>("/settings", data);
  return transformSettings(response.data);
}

export async function fetchAgentTools(): Promise<AgentToolMetadata[]> {
  const response = await apiClient.get<
    Array<{
      key: string;
      name: string;
      description: string;
      is_readonly: boolean;
    }>
  >("/agent/tools");
  return response.data.map((tool) => ({
    key: tool.key,
    name: tool.name,
    description: tool.description,
    isReadonly: tool.is_readonly,
  }));
}
