import { net } from "electron";
import { createWriteStream } from "node:fs";
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { spawn } from "node:child_process";
import { Transform } from "node:stream";

export async function downloadFile(
  url: string,
  outputPath: string,
  onProgress?: (received: number, total: number) => void,
): Promise<void> {
  await mkdir(path.dirname(outputPath), { recursive: true });
  const response = await net.fetch(url);
  if (!response.ok || !response.body) {
    throw new Error(`failed to download ${url}: ${response.status}`);
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

export async function extractTarGz(
  archivePath: string,
  outputDir: string,
  onProgress?: (entryName: string) => void,
): Promise<void> {
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await new Promise<void>((resolve, reject) => {
    const child = spawn("tar", ["-xzf", archivePath, "-C", outputDir], {
      windowsHide: true,
      stdio: ["ignore", "pipe", "inherit"],
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`tar exited with code ${code}`));
    });
    if (onProgress && child.stdout) {
      child.stdout.on("data", (chunk: Buffer) => {
        const lines = chunk.toString("utf8").split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed) onProgress(trimmed);
        }
      });
    }
  });
}
