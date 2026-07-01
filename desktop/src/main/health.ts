import type { ChildProcess } from "node:child_process";

const DEFAULT_TIMEOUT_MS = 60_000;

interface WaitForBackendOptions {
  process?: ChildProcess;
  timeoutMs?: number;
}

export async function waitForBackend(baseUrl: string, options: WaitForBackendOptions | number = DEFAULT_TIMEOUT_MS): Promise<void> {
  const timeoutMs = typeof options === "number" ? options : (options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const backendProcess = typeof options === "number" ? undefined : options.process;
  const startedAt = Date.now();
  const healthUrl = `${baseUrl.replace(/\/+$/, "")}/api/v1/health`;

  while (Date.now() - startedAt < timeoutMs) {
    if (backendProcess && backendProcess.exitCode !== null) {
      throw new Error(`backend process exited before health check: ${healthUrl} (code ${backendProcess.exitCode})`);
    }

    try {
      const response = await fetch(healthUrl);
      if (response.ok) return;
    } catch {
      // Retry until timeout.
    }

    if (backendProcess && backendProcess.signalCode) {
      throw new Error(`backend process exited before health check: ${healthUrl} (signal ${backendProcess.signalCode})`);
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`backend health check timeout: ${healthUrl}`);
}
