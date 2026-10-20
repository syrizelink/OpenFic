import { apiClient } from "@/lib/api-client";

export interface PluginDiagnostic {
  sequence: number;
  time: string;
  pluginId: string;
  viewId?: string;
  kind: string;
  method: string;
  status: string;
  durationMs?: number;
  request?: unknown;
  result?: unknown;
  error?: unknown;
}
let enabled = false;
let pending = 0;
export function enablePluginDiagnostics(value: boolean) {
  enabled = value;
}
export function pluginDiagnosticsEnabled() {
  return enabled;
}
export function addPluginDiagnostic(item: Omit<PluginDiagnostic, "sequence" | "time">) {
  if (!enabled || pending >= 8) return;
  const payload =
    JSON.stringify(item).length <= 64000
      ? item
      : {
          ...item,
          request: "[payload truncated]",
          result: "[payload truncated]",
          error: item.status === "error" ? "[error payload truncated]" : undefined,
        };
  pending++;
  // The server redacts actual configured secret values before retaining anything.
  // No raw frontend history, localStorage or cross-window debug messages are used.
  void apiClient
    .post(`/plugins/${item.pluginId}/inspector/report`, payload)
    .catch(() => {})
    .finally(() => {
      pending--;
    });
}
export async function diagnosticCall<T>(
  pluginId: string,
  kind: string,
  method: string,
  request: unknown,
  invoke: () => Promise<T>,
  viewId?: string,
): Promise<T> {
  if (!enabled) return invoke();
  const start = performance.now();
  try {
    const result = await invoke();
    addPluginDiagnostic({
      pluginId,
      viewId,
      kind,
      method,
      request,
      result,
      status: "ok",
      durationMs: performance.now() - start,
    });
    return result;
  } catch (error) {
    addPluginDiagnostic({
      pluginId,
      viewId,
      kind,
      method,
      request,
      error: error instanceof Error ? error.message : String(error),
      status: "error",
      durationMs: performance.now() - start,
    });
    throw error;
  }
}
