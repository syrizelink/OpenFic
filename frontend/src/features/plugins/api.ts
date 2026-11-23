import axios, { type AxiosRequestConfig } from "axios";

import { apiClient } from "@/lib/api-client";

export interface PluginView {
  id: string;
  title: string;
  renderer?: "iframe" | "declarative";
  entry?: string;
  render?: string;
  action?: string;
  status?: string;
  slot: string;
  height?: number;
  icon?: string | null;
  presentation?: "popover" | "dialog" | "action" | "none" | null;
  placement?: "left-end" | "right-start" | "right-end" | null;
  showCloseButton?: boolean | null;
  selectionTriggers?: ("selection" | "contextmenu")[] | null;
  selectionSources?:
    | ("chapter" | "note" | "character" | "world-info" | "agent-message" | "agent-input")[]
    | null;
}
export interface PluginSetting {
  key: string;
  label: string;
  type: "string" | "boolean" | "integer" | "json" | "number" | "select";
  default: unknown;
  options?: { value: string; label: string }[];
  minimum?: number;
  maximum?: number;
  secret?: boolean;
  required?: boolean;
  description?: string;
}
export interface InstalledPlugin {
  entry?: string | null;
  resources?: string[];
  id: string;
  name: string;
  version: string;
  description: string;
  detail?: string | null;
  homepage?: string | null;
  icon?: string | null;
  author: string;
  reload_revision?: number;
  enabled: boolean;
  status: "enabled" | "disabled" | "error";
  error: string | null;
  capabilities: string[];
  views: PluginView[];
  settings: PluginSetting[];
  configuration: Record<string, unknown>;
  configured_secrets?: string[];
  tools?: string[];
  hooks?: string[];
  graphs?: string[];
}
export const PLUGINS_QUERY_KEY = ["plugins"] as const;
export async function fetchPlugins(): Promise<InstalledPlugin[]> {
  return (await apiClient.get<{ plugins: InstalledPlugin[] }>("/plugins")).data.plugins;
}
export const pluginsQueryOptions = {
  queryKey: PLUGINS_QUERY_KEY,
  queryFn: fetchPlugins,
  staleTime: Infinity,
};
export async function savePluginOrder(pluginIds: string[]): Promise<void> {
  await apiClient.put("/plugins/order", { plugin_ids: pluginIds });
}
export async function installPlugin(
  file: File,
  operationId: string,
  updateId?: string,
  onUploadProgress?: AxiosRequestConfig["onUploadProgress"],
): Promise<InstalledPlugin> {
  const data = new FormData();
  data.append("file", file);
  data.append("trusted", "true");
  data.append("operation_id", operationId);
  const response = await apiClient[updateId ? "put" : "post"]<InstalledPlugin>(
    updateId ? `/plugins/${encodeURIComponent(updateId)}/package` : "/plugins",
    data,
    { headers: { "Content-Type": "multipart/form-data" }, onUploadProgress, timeout: 180_000 },
  );
  return response.data;
}
export async function installPluginFromRepository(
  url: string,
  operationId: string,
): Promise<InstalledPlugin> {
  const response = await apiClient.post<InstalledPlugin>(
    "/plugins/repository",
    { url, trusted: true, operation_id: operationId },
    { timeout: 180_000 },
  );
  return response.data;
}
export function pluginError(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === "string") {
    return error.response.data.detail;
  }
  return error instanceof Error ? error.message : String(error);
}
export async function downloadPlugin(plugin: InstalledPlugin): Promise<void> {
  const { data } = await apiClient.get(`/plugins/${plugin.id}/package`, { responseType: "blob" });
  savePluginDownload(data, `${plugin.id}-${plugin.version}.zip`);
}

export interface PluginLogEntry {
  time: string;
  level: string;
  action: string;
  message: string;
}

function pluginLogsPath(pluginId: string) {
  return `/plugins/${encodeURIComponent(pluginId)}/logs`;
}

export async function fetchPluginLogs(
  pluginId: string,
  params: { minutes?: number; limit?: number },
  signal: AbortSignal,
): Promise<PluginLogEntry[]> {
  return (await apiClient.get<PluginLogEntry[]>(pluginLogsPath(pluginId), { params, signal })).data;
}

export async function clearPluginLogs(pluginId: string): Promise<void> {
  await apiClient.delete(pluginLogsPath(pluginId));
}

export async function downloadPluginLogs(pluginId: string): Promise<void> {
  const { data } = await apiClient.get<Blob>(`${pluginLogsPath(pluginId)}/download`, {
    responseType: "blob",
  });
  savePluginDownload(data, `${pluginId}.log`);
}

function savePluginDownload(data: Blob, filename: string) {
  const url = URL.createObjectURL(data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
