const DEFAULT_TIMEOUT_MS = 60_000;

export async function waitForBackend(baseUrl: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  const startedAt = Date.now();
  const healthUrl = `${baseUrl.replace(/\/+$/, "")}/api/v1/health`;

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(healthUrl);
      if (response.ok) return;
    } catch {
      // Retry until timeout.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`backend health check timeout: ${healthUrl}`);
}
