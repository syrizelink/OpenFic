import { net } from "electron";
import type { ChildProcess } from "node:child_process";

const DEFAULT_TIMEOUT_MS = 60_000;
const MAINTENANCE_TIMEOUT_MS = 60 * 60_000;

export interface BackendHealth {
  status: "healthy";
  version: string | null;
}

interface WaitForBackendOptions {
  process?: ChildProcess;
  timeoutMs?: number | null;
  signal?: AbortSignal;
}

export function throwIfAborted(signal?: AbortSignal): void {
  if (!signal?.aborted) return;
  const error = new Error("连接已取消");
  error.name = "AbortError";
  throw error;
}

export function parseBackendHealth(value: unknown): BackendHealth | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as { status?: unknown; version?: unknown };
  if (candidate.status !== "healthy") return null;
  if (candidate.version !== undefined && typeof candidate.version !== "string") return null;
  return { status: "healthy", version: candidate.version ?? null };
}

function createBackendExitError(healthUrl: string, code: number | null, signal: NodeJS.Signals | null): Error {
  if (signal) return new Error(`backend process exited before health check: ${healthUrl} (signal ${signal})`);
  return new Error(`backend process exited before health check: ${healthUrl} (code ${code ?? "unknown"})`);
}

function isLoopbackUrl(url: string): boolean {
  try {
    const { hostname } = new URL(url);
    return hostname === "localhost" || hostname === "::1" || hostname === "[::1]" || hostname.startsWith("127.");
  } catch {
    return false;
  }
}

export async function waitForBackend(
  baseUrl: string,
  options: WaitForBackendOptions | number | null = DEFAULT_TIMEOUT_MS,
): Promise<BackendHealth> {
  const timeoutMs =
    typeof options === "number" ? options : (options?.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const backendProcess = typeof options === "number" || options === null ? undefined : options.process;
  const externalSignal = typeof options === "number" || options === null ? undefined : options.signal;
  const healthUrl = `${baseUrl.replace(/\/+$/, "")}/api/v1/health`;
  const controller = new AbortController();
  let processError: Error | null = null;

  const onExit = (code: number | null, signal: NodeJS.Signals | null) => {
    processError = createBackendExitError(healthUrl, code, signal);
    controller.abort();
  };
  const onError = (error: Error) => {
    processError = new Error(`backend process failed before health check: ${healthUrl} (${error.message})`);
    controller.abort();
  };

  if (backendProcess && backendProcess.exitCode !== null) {
    throw createBackendExitError(healthUrl, backendProcess.exitCode, backendProcess.signalCode);
  }

  const abortWait = () => controller.abort();
  throwIfAborted(externalSignal);
  externalSignal?.addEventListener("abort", abortWait, { once: true });
  backendProcess?.once("exit", onExit);
  backendProcess?.once("error", onError);
  const timeout = timeoutMs === null ? undefined : setTimeout(() => controller.abort(), timeoutMs);

  try {
    while (!controller.signal.aborted) {
      try {
        // Node's HTTP stack is deliberately used for the local backend so its
        // health checks never depend on Chromium's system proxy configuration.
        const response = isLoopbackUrl(healthUrl)
          ? await fetch(healthUrl, { signal: controller.signal })
          : await net.fetch(healthUrl, { signal: controller.signal });
        const health = parseBackendHealth(await response.json().catch(() => null));
        if (response.ok && health) return health;
      } catch {
        if (processError) throw processError;
      }

      if (processError) throw processError;

      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, 500);
        controller.signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);
            resolve();
          },
          { once: true },
        );
      });
    }

    throwIfAborted(externalSignal);
    if (processError) throw processError;
    throw new Error(`backend health check timeout: ${healthUrl}`);
  } finally {
    clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortWait);
    backendProcess?.off("exit", onExit);
    backendProcess?.off("error", onError);
  }
}

export type BackendMaintenancePhase =
  | "pending"
  | "pruning"
  | "migrating"
  | "vacuuming"
  | "cleanup"
  | "ready"
  | "failed";

export interface BackendMaintenanceStatus {
  status: "pending" | "running" | "ready" | "failed";
  phase: BackendMaintenancePhase;
  progress: number | null;
  error: string | null;
}

interface WaitForBackendMaintenanceOptions {
  process?: ChildProcess;
  signal?: AbortSignal;
  timeoutMs?: number | null;
  onProgress?: (status: BackendMaintenanceStatus) => void;
}

export function parseBackendMaintenanceStatus(value: unknown): BackendMaintenanceStatus | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as {
    status?: unknown;
    phase?: unknown;
    progress?: unknown;
    error?: unknown;
  };
  const statuses = new Set(["pending", "running", "ready", "failed"]);
  if (
    typeof candidate.status !== "string" ||
    !statuses.has(candidate.status) ||
    typeof candidate.phase !== "string"
  ) {
    return null;
  }
  const progress = candidate.progress === null || candidate.progress === undefined
    ? null
    : typeof candidate.progress === "number" &&
        Number.isFinite(candidate.progress) &&
        candidate.progress >= 0 &&
        candidate.progress <= 1
      ? candidate.progress
      : undefined;
  if (progress === undefined) return null;
  return {
    status: candidate.status as BackendMaintenanceStatus["status"],
    phase: candidate.phase as BackendMaintenancePhase,
    progress,
    error: typeof candidate.error === "string" ? candidate.error : null,
  };
}

export async function waitForBackendMaintenance(
  baseUrl: string,
  options: WaitForBackendMaintenanceOptions = {},
): Promise<BackendMaintenanceStatus> {
  const statusUrl = `${baseUrl.replace(/\/+$/, "")}/api/v1/health/maintenance`;
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? MAINTENANCE_TIMEOUT_MS;
  let processError: Error | null = null;
  let timedOut = false;

  const onExit = (code: number | null, signal: NodeJS.Signals | null) => {
    processError = createBackendExitError(statusUrl, code, signal);
    controller.abort();
  };
  const onError = (error: Error) => {
    processError = new Error(`backend process failed during maintenance: ${statusUrl} (${error.message})`);
    controller.abort();
  };
  const abortWait = () => controller.abort();
  const timeout = timeoutMs === null
    ? undefined
    : setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);

  options.signal?.addEventListener("abort", abortWait, { once: true });
  options.process?.once("exit", onExit);
  options.process?.once("error", onError);

  try {
    while (!controller.signal.aborted) {
      try {
        const response = isLoopbackUrl(statusUrl)
          ? await fetch(statusUrl, { signal: controller.signal })
          : await net.fetch(statusUrl, { signal: controller.signal });
        const maintenance = parseBackendMaintenanceStatus(
          await response.json().catch(() => null),
        );
        if (response.ok && maintenance) {
          options.onProgress?.(maintenance);
          if (maintenance.status === "ready") return maintenance;
          if (maintenance.status === "failed") {
            const error = new Error(
              maintenance.error ?? "backend database maintenance failed",
            );
            error.name = "BackendMaintenanceError";
            throw error;
          }
        }
      } catch (error) {
        if (processError) throw processError;
        if (error instanceof Error && error.name === "AbortError") break;
        if (error instanceof Error && error.name === "BackendMaintenanceError") {
          throw error;
        }
      }

      await new Promise<void>((resolve) => {
        const onAbort = () => {
          clearTimeout(timer);
          resolve();
        };
        const timer = setTimeout(() => {
          controller.signal.removeEventListener("abort", onAbort);
          resolve();
        }, 500);
        controller.signal.addEventListener("abort", onAbort, { once: true });
      });
    }

    throwIfAborted(options.signal);
    if (processError) throw processError;
    if (timedOut) {
      throw new Error(`backend maintenance timed out after ${timeoutMs}ms`);
    }
    throw new Error(`backend maintenance status unavailable: ${statusUrl}`);
  } finally {
    if (timeout) clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortWait);
    options.process?.off("exit", onExit);
    options.process?.off("error", onError);
  }
}
