import { spawn } from "node:child_process";
import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, rm, symlink } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { createGunzip } from "node:zlib";
import { extract } from "tar-stream";

function resolveArchiveEntryPath(outputDir: string, entryName: string): string {
  const outputRoot = path.resolve(outputDir);
  const entryPath = path.resolve(outputRoot, entryName);
  if (entryPath === outputRoot || !entryPath.startsWith(`${outputRoot}${path.sep}`)) {
    throw new Error(`archive entry escapes output directory: ${entryName}`);
  }
  return entryPath;
}

function resolveArchiveLinkPath(outputDir: string, entryPath: string, linkName: string): void {
  if (path.isAbsolute(linkName)) throw new Error(`archive link escapes output directory: ${linkName}`);
  const outputRoot = path.resolve(outputDir);
  const linkTarget = path.resolve(path.dirname(entryPath), linkName);
  if (!linkTarget.startsWith(`${outputRoot}${path.sep}`)) {
    throw new Error(`archive link escapes output directory: ${linkName}`);
  }
}

function logProcessOutput(stream: NodeJS.ReadableStream, onLog?: (message: string) => void): void {
  let buffer = "";
  stream.on("data", (chunk: Buffer | string) => {
    buffer += (typeof chunk === "string" ? chunk : chunk.toString("utf8")).replace(/\r/g, "\n");
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) onLog?.(line);
    }
  });
  stream.on("end", () => {
    if (buffer.trim()) onLog?.(buffer);
  });
}

async function extractWithSystemTar(archivePath: string, outputDir: string, onLog?: (message: string) => void): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    onLog?.(`执行解压命令：tar -xzf ${archivePath} -C ${outputDir}`);
    const child = spawn("tar", ["-xzf", archivePath, "-C", outputDir], {
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    logProcessOutput(child.stdout, onLog);
    logProcessOutput(child.stderr, onLog);
    child.once("error", (error) => {
      onLog?.(`解压命令启动失败：${error.message}`);
      reject(error);
    });
    child.once("exit", (code) => {
      if (code === 0) {
        onLog?.("解压命令执行完成");
        resolve();
        return;
      }
      const error = new Error(`tar exited with code ${code}`);
      onLog?.(`解压命令执行失败：${error.message}`);
      reject(error);
    });
  });
}

async function extractWithBuiltInTar(archivePath: string, outputDir: string): Promise<void> {
  const archive = extract();
  archive.on("entry", (header, stream, next) => {
    const extractEntry = async () => {
      const entryPath = resolveArchiveEntryPath(outputDir, header.name);
      if (header.type === "directory") {
        await mkdir(entryPath, { recursive: true });
        stream.resume();
        return;
      }
      if (header.type === "file") {
        await mkdir(path.dirname(entryPath), { recursive: true });
        await pipeline(stream, createWriteStream(entryPath, { mode: header.mode }));
        return;
      }
      if (header.type === "symlink" && header.linkname) {
        resolveArchiveLinkPath(outputDir, entryPath, header.linkname);
        await mkdir(path.dirname(entryPath), { recursive: true });
        await symlink(header.linkname, entryPath);
        stream.resume();
        return;
      }
      stream.resume();
    };

    void extractEntry().then(() => next(), next);
  });

  await pipeline(createReadStream(archivePath), createGunzip(), archive);
}

export async function extractTarGz(archivePath: string, outputDir: string, onLog?: (message: string) => void): Promise<void> {
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });

  try {
    await extractWithSystemTar(archivePath, outputDir, onLog);
  } catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
    onLog?.("未找到系统 tar，改用内置解压器");
    await rm(outputDir, { recursive: true, force: true });
    await mkdir(outputDir, { recursive: true });
    await extractWithBuiltInTar(archivePath, outputDir);
  }
}
