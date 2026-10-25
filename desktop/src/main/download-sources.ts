import { net } from "electron";
import { readDesktopConfig } from "./config.js";
import { configureDefaultSystemProxy } from "./proxy.js";
import type { DownloadSourcePreference } from "../shared/config.js";
export { orderDownloadSources, type DownloadSource } from "./source-selection.js";

export async function getDownloadSourcePreference(): Promise<DownloadSourcePreference> {
  return (await readDesktopConfig())?.downloadSource ?? "auto";
}

/** Timeout covers redirects and the entire small metadata body. Never retain signed redirect URLs. */
export async function fetchSourceText(url: string, fetcher: typeof net.fetch = net.fetch): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetcher(url, { signal: controller.signal, cache: "no-store" });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return await response.text();
  } finally {
    clearTimeout(timer);
  }
}

export async function probeDownloadUrl(url: string): Promise<void> {
  await configureDefaultSystemProxy();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  try {
    // A small GET measures the real redirected download path; some mirrors reject HEAD.
    const response = await net.fetch(url, { signal: controller.signal, headers: { Range: "bytes=0-65535" } });
    if (!response.ok || !response.body) throw new Error(`${url}: HTTP ${response.status}`);
    const reader = response.body.getReader();
    try {
      const chunk = await reader.read();
      if (chunk.done) throw new Error(`Empty download: ${url}`);
    } finally {
      await reader.cancel();
    }
  } finally {
    clearTimeout(timer);
  }
}
