import { net } from "electron";
import { createWriteStream } from "node:fs";
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { Transform } from "node:stream";
export { extractTarGz } from "./tar-extract.js";

const FIRST_BYTE_TIMEOUT_MS = 8_000;

type FetchResponse = Awaited<ReturnType<typeof net.fetch>>;

async function fetchWithFirstByteTimeout(url: string): Promise<FetchResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FIRST_BYTE_TIMEOUT_MS);
  try {
    return await net.fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function streamResponseToPath(
  response: FetchResponse,
  outputPath: string,
  onProgress?: (received: number, total: number) => void,
): Promise<void> {
  if (!response.ok || !response.body) {
    throw new Error(`download responded with status ${response.status}`);
  }

  const total = Number(response.headers.get("content-length") ?? 0);

  if (!onProgress) {
    await pipeline(response.body, createWriteStream(outputPath));
    return;
  }

  let received = 0;
  const counting = new Transform({
    transform(chunk, _encoding, callback) {
      received += chunk.length;
      onProgress(received, total);
      callback(null, chunk);
    },
  });

  await pipeline(response.body, counting, createWriteStream(outputPath));
}

export async function downloadFile(
  urls: string[],
  outputPath: string,
  onProgress?: (received: number, total: number) => void,
  onLog?: (message: string) => void,
): Promise<void> {
  if (urls.length === 0) throw new Error("no download urls provided");
  await mkdir(path.dirname(outputPath), { recursive: true });

  let lastError: unknown;
  for (const url of urls) {
    try {
      onLog?.(`下载文件：${url}`);
      const response = await fetchWithFirstByteTimeout(url);
      await streamResponseToPath(response, outputPath, onProgress);
      onLog?.(`文件下载完成：${url}`);
      return;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      onLog?.(`文件下载失败：${url}：${message}`);
      lastError = new Error(`failed to download ${url}: ${message}`);
      await rm(outputPath, { force: true });
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}
