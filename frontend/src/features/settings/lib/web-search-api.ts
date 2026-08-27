/**
 * Web Search Settings API
 *
 * 联网搜索设置 API 客户端。
 */

import { apiClient } from "@/lib/api-client";

export interface WebSearchProviderField {
  key: string;
  fieldType: "text" | "select";
  required: boolean;
  options: string[];
}

export interface WebSearchProviderInfo {
  name: string;
  requiresApiKey: boolean;
  fields: WebSearchProviderField[];
}

export interface WebSearchSettings {
  enabled: boolean;
  provider: string;
  hasApiKeys: Record<string, boolean>;
  maxResults: number;
  domainFilters: string[];
  extras: Record<string, string>;
}

export interface WebSearchSettingsUpdateRequest {
  enabled?: boolean;
  provider?: string;
  api_key?: string;
  max_results?: number;
  domain_filters?: string[];
  extras?: Record<string, string>;
}

interface WebSearchSettingsResponse {
  enabled: boolean;
  provider: string;
  has_api_keys: Record<string, boolean>;
  max_results: number;
  domain_filters: string[];
  extras: Record<string, string>;
}

interface WebSearchProviderInfoResponse {
  name: string;
  requires_api_key: boolean;
  fields: Array<{
    key: string;
    field_type: string;
    required: boolean;
    options: string[];
  }>;
}

function transformWebSearchSettings(raw: WebSearchSettingsResponse): WebSearchSettings {
  return {
    enabled: raw.enabled,
    provider: raw.provider,
    hasApiKeys: raw.has_api_keys ?? {},
    maxResults: raw.max_results,
    domainFilters: raw.domain_filters ?? [],
    extras: raw.extras ?? {},
  };
}

function transformWebSearchProviderInfo(raw: WebSearchProviderInfoResponse): WebSearchProviderInfo {
  return {
    name: raw.name,
    requiresApiKey: raw.requires_api_key,
    fields: raw.fields.map((field) => ({
      key: field.key,
      fieldType: field.field_type === "select" ? "select" : "text",
      required: field.required,
      options: field.options ?? [],
    })),
  };
}

export async function fetchWebSearchSettings(): Promise<WebSearchSettings> {
  const response = await apiClient.get<WebSearchSettingsResponse>("/settings/web-search");
  return transformWebSearchSettings(response.data);
}

export async function updateWebSearchSettings(
  data: WebSearchSettingsUpdateRequest,
): Promise<WebSearchSettings> {
  const response = await apiClient.put<WebSearchSettingsResponse>("/settings/web-search", data);
  return transformWebSearchSettings(response.data);
}

export async function fetchWebSearchProviders(): Promise<WebSearchProviderInfo[]> {
  const response = await apiClient.get<WebSearchProviderInfoResponse[]>(
    "/settings/web-search/providers",
  );
  return response.data.map(transformWebSearchProviderInfo);
}
