import axios from "axios";

import { apiClient } from "@/lib/api-client";

export interface PluginView {
  id: string;
  title: string;
  renderer?: "iframe" | "declarative";
  entry?: string;
  render?: string;
  action?: string;
  slot: string;
  height?: number;
}
export interface PluginSetting {
  key: string;
  label: string;
  type: "string" | "boolean" | "integer" | "json" | "number";
  default: string | boolean | number;
  minimum?: number;
  maximum?: number;
  secret?: boolean;
  description?: string;
}
export interface InstalledPlugin {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  status: "enabled" | "disabled" | "error";
  error: string | null;
  capabilities: string[];
  views: PluginView[];
  settings: PluginSetting[];
  configuration: Record<string, unknown>;
  format?: "openfic" | "claude-mod";
  compatibility?: { warnings?: string[]; supported?: string[]; [key: string]: unknown };
  tools?: string[];
  hooks?: string[];
  graphs?: string[];
}
export const PLUGINS_QUERY_KEY = ["plugins"] as const;
export async function fetchPlugins(): Promise<InstalledPlugin[]> {
  return (await apiClient.get<{ plugins: InstalledPlugin[] }>("/plugins")).data.plugins;
}
export async function installPlugin(file: File, updateId?: string): Promise<void> {
  const data = new FormData();
  data.append("file", file);
  data.append("trusted", "true");
  await apiClient[updateId ? "put" : "post"](
    updateId ? `/plugins/${updateId}/package` : "/plugins",
    data,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
}
export function pluginError(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === "string") {
    return error.response.data.detail;
  }
  return error instanceof Error ? error.message : String(error);
}
export async function downloadPlugin(plugin: InstalledPlugin): Promise<void> {
  const { data } = await apiClient.get(`/plugins/${plugin.id}/package`, { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${plugin.id}-${plugin.version}.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
}
