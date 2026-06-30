export interface RuntimeConfig {
  backendBaseUrl: string;
}

let runtimeConfigPromise: Promise<RuntimeConfig | null> | null = null;
let runtimeConfig: RuntimeConfig | null = null;

function normalizeBackendBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}

function isRuntimeConfig(value: unknown): value is RuntimeConfig {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { backendBaseUrl?: unknown };
  return typeof candidate.backendBaseUrl === "string" && candidate.backendBaseUrl.length > 0;
}

export async function loadRuntimeConfig(): Promise<RuntimeConfig | null> {
  if (runtimeConfigPromise) return runtimeConfigPromise;

  runtimeConfigPromise = fetch("/runtime-config.json", { cache: "no-store" })
    .then(async (response) => {
      if (!response.ok) return null;
      const data = (await response.json()) as unknown;
      if (!isRuntimeConfig(data)) return null;
      runtimeConfig = {
        backendBaseUrl: normalizeBackendBaseUrl(data.backendBaseUrl),
      };
      return runtimeConfig;
    })
    .catch(() => null);

  return runtimeConfigPromise;
}

export function getRuntimeConfig(): RuntimeConfig | null {
  return runtimeConfig;
}
