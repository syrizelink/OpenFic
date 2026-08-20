import { spawn } from "node:child_process";
import { createReadStream, createWriteStream } from "node:fs";
import { cp, lstat, mkdir, mkdtemp, readdir, readlink, rm, stat, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { createGunzip } from "node:zlib";
import { extract } from "tar-stream";
import { BACKUP_MANIFEST_NAME, hashFile, verifyBackupManifest } from "../backup-manifest.js";
import type { DataOperationPhase } from "../../shared/ipc.js";

const EXCLUDED_RUNTIME_ENTRIES = new Set([
  "Cache",
  "Code Cache",
  "GPUCache",
  "DawnCache",
  "DawnGraphiteCache",
  "DawnWebGPUCache",
  "GrShaderCache",
  "ShaderCache",
  "Crashpad",
  "Session Storage",
  "WebStorage",
  "lockfile",
  "SingletonLock",
  "SingletonCookie",
  "SingletonSocket",
]);

export function isExcludedRuntimeEntry(name: string): boolean {
  return EXCLUDED_RUNTIME_ENTRIES.has(name);
}

function isLockError(error: unknown): boolean {
  const code = (error as NodeJS.ErrnoException).code;
  return code === "EBUSY" || code === "EPERM" || code === "EACCES";
}

export type DataPhaseReporter = (phase: DataOperationPhase, progress?: number) => void;

const BACKUP_RETRY_ATTEMPTS = 5;
const BACKUP_RETRY_BASE_DELAY_MS = 250;

async function assertNoSymlink(entryPath: string): Promise<void> {
  const info = await lstat(entryPath);
  if (info.isSymbolicLink()) {
    throw new Error(`拒绝处理符号链接：${entryPath}`);
  }
  if (info.isDirectory()) {
    const entries = await readdir(entryPath, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isSymbolicLink()) {
        throw new Error(`拒绝处理符号链接：${path.join(entryPath, entry.name)}`);
      }
      if (entry.isDirectory()) await assertNoSymlink(path.join(entryPath, entry.name));
    }
  }
}

export async function assertDirNoSymlink(dir: string): Promise<void> {
  try {
    await lstat(dir);
  } catch {
    return;
  }
  await assertNoSymlink(dir);
}

export async function copyWithRetry(sourcePath: string, targetPath: string): Promise<void> {
  await assertNoSymlink(sourcePath);
  for (let attempt = 1; ; attempt++) {
    try {
      await cp(sourcePath, targetPath, { recursive: true });
      return;
    } catch (error) {
      if (attempt >= BACKUP_RETRY_ATTEMPTS || !isLockError(error)) throw error;
      await new Promise((resolve) => setTimeout(resolve, BACKUP_RETRY_BASE_DELAY_MS * attempt));
    }
  }
}

export async function measureTreeSize(entryPath: string): Promise<number> {
  const info = await lstat(entryPath);
  if (info.isSymbolicLink()) return 0;
  if (info.isDirectory()) {
    let total = 0;
    const entries = await readdir(entryPath, { withFileTypes: true });
    for (const entry of entries) {
      if (isExcludedRuntimeEntry(entry.name)) continue;
      total += await measureTreeSize(path.join(entryPath, entry.name));
    }
    return total;
  }
  return info.size;
}

export async function copyTree(
  sourcePath: string,
  targetPath: string,
  onLog?: (message: string) => void,
  onBytesCopied?: (bytes: number) => void,
  preserveSymlinks: boolean = false,
): Promise<void> {
  const sourceStat = await lstat(sourcePath);
  if (sourceStat.isSymbolicLink()) {
    if (!preserveSymlinks) {
      onLog?.(`跳过符号链接：${sourcePath}`);
      return;
    }
    const link = await readlink(sourcePath);
    if (path.isAbsolute(link)) {
      onLog?.(`跳过绝对路径符号链接：${sourcePath} -> ${link}`);
      return;
    }
    await mkdir(path.dirname(targetPath), { recursive: true });
    await symlink(link, targetPath);
    return;
  }
  if (sourceStat.isDirectory()) {
    await mkdir(targetPath, { recursive: true });
    const entries = await readdir(sourcePath, { withFileTypes: true });
    for (const entry of entries) {
      if (isExcludedRuntimeEntry(entry.name)) continue;
      await copyTree(path.join(sourcePath, entry.name), path.join(targetPath, entry.name), onLog, onBytesCopied, preserveSymlinks);
    }
    return;
  }
  try {
    await cp(sourcePath, targetPath);
  } catch (error) {
    if (isLockError(error)) {
      onLog?.(`跳过被占用的文件：${targetPath}（${(error as NodeJS.ErrnoException).code}）`);
      return;
    }
    throw error;
  }
  onBytesCopied?.(sourceStat.size);
}

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

export async function extractTarGz(
  archivePath: string,
  outputDir: string,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
  verifyBackup: boolean = true,
): Promise<void> {
  const stagingDir = await mkdtemp(path.join(os.tmpdir(), "openfic-restore-"));
  const rollbackDir = await mkdtemp(path.join(os.tmpdir(), "openfic-rollback-"));
  let rollbackKept = false;
  const preserveSymlinks = !verifyBackup;
  try {
    onPhase?.("extract");
    await extractIntoDirectory(archivePath, stagingDir, onLog);
    if (verifyBackup) {
      onPhase?.("verify");
      await verifyBackupManifest(stagingDir);
      await assertDirNoSymlink(outputDir);
    }
    await copyTopLevelEntries(outputDir, rollbackDir, "rollback", onLog, onPhase, preserveSymlinks);
    try {
      await copyTopLevelEntries(stagingDir, outputDir, "copy", onLog, onPhase, preserveSymlinks);
      if (verifyBackup) await verifyRestoredFiles(stagingDir, outputDir);
      onPhase?.("cleanup");
      await clearExtraEntries(outputDir, stagingDir, onLog);
    } catch (error) {
      try {
        await clearTopLevelEntries(outputDir, onLog);
        await copyTopLevelEntries(rollbackDir, outputDir, "copy", onLog, onPhase, preserveSymlinks);
      } catch (rollbackError) {
        rollbackKept = true;
        const detail = rollbackError instanceof Error ? rollbackError.message : String(rollbackError);
        throw new Error(
          `还原失败，且自动回滚失败：${detail}。已保留回滚备份目录 ${rollbackDir}，可手动将其内容复制回 ${outputDir}`,
          { cause: error },
        );
      }
      throw error;
    }
  } finally {
    await rm(stagingDir, { recursive: true, force: true });
    if (!rollbackKept) await rm(rollbackDir, { recursive: true, force: true });
  }
}

async function extractIntoDirectory(archivePath: string, outputDir: string, onLog?: (message: string) => void): Promise<void> {
  try {
    await extractWithSystemTar(archivePath, outputDir, onLog);
  } catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
    onLog?.("未找到系统 tar，改用内置解压器");
    await extractWithBuiltInTar(archivePath, outputDir);
  }
}

async function copyTopLevelEntries(
  sourceDir: string,
  targetDir: string,
  phase: DataOperationPhase,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
  preserveSymlinks: boolean = false,
): Promise<void> {
  let entries;
  try {
    entries = await readdir(sourceDir, { withFileTypes: true });
  } catch {
    return;
  }
  let total = 0;
  const coreSizes = new Map<string, number>();
  const copyable: { name: string; core: boolean }[] = [];
  for (const entry of entries) {
    if (isExcludedRuntimeEntry(entry.name)) continue;
    if (entry.name === BACKUP_MANIFEST_NAME) continue;
    const name = entry.name;
    const size = await measureTreeSize(path.join(sourceDir, name));
    copyable.push({ name, core: CORE_DATA_ENTRIES.has(name) });
    if (CORE_DATA_ENTRIES.has(name)) coreSizes.set(name, size);
    total += size;
  }
  let copied = 0;
  let lastRounded = -1;
  const report = () => {
    const rounded = total > 0 ? Math.floor((copied / total) * 100) : 100;
    if (rounded !== lastRounded) {
      lastRounded = rounded;
      onPhase?.(phase, rounded / 100);
    }
  };
  for (const { name, core } of copyable) {
    const sourcePath = path.join(sourceDir, name);
    const targetPath = path.join(targetDir, name);
    if (core) {
      await copyWithRetry(sourcePath, targetPath);
      copied += coreSizes.get(name) ?? 0;
      report();
    } else {
      await copyTree(sourcePath, targetPath, onLog, (bytes) => {
        copied += bytes;
        report();
      }, preserveSymlinks);
    }
  }
  report();
}

async function clearTopLevelEntries(dir: string, onLog?: (message: string) => void): Promise<void> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (isExcludedRuntimeEntry(entry.name)) continue;
    await removeEntry(path.join(dir, entry.name), onLog);
  }
}

async function removeEntry(fullPath: string, onLog?: (message: string) => void): Promise<void> {
  try {
    await rm(fullPath, { recursive: true, force: true });
  } catch (error) {
    if (isLockError(error)) {
      onLog?.(`保留被占用的文件：${fullPath}（${(error as NodeJS.ErrnoException).code}）`);
      return;
    }
    throw error;
  }
}

async function clearExtraEntries(dir: string, keepDir: string, onLog?: (message: string) => void): Promise<void> {
  let keep: Set<string>;
  try {
    keep = new Set(await readdir(keepDir));
  } catch {
    return;
  }
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (isExcludedRuntimeEntry(entry.name)) continue;
    if (entry.name === BACKUP_MANIFEST_NAME) {
      await removeEntry(path.join(dir, entry.name), onLog);
      continue;
    }
    if (keep.has(entry.name)) continue;
    await removeEntry(path.join(dir, entry.name), onLog);
  }
}

export const CORE_DATA_ENTRIES = new Set(["openfic.db", ".key", "covers"]);

export const INSTANCE_DATA_ENTRIES = new Set([
  ".env",
  ".key",
  "openfic.db",
  "openfic.db-wal",
  "openfic.db-shm",
  "checkpoints.db",
  "checkpoints.db-wal",
  "checkpoints.db-shm",
  "covers",
  "character-images",
  "agent-attachments",
  "chapter-exports",
  "lancedb",
  "fastembed_cache",
  "model_provider_catalog",
  "icons",
]);

function isCoreDataPath(relativePath: string): boolean {
  return CORE_DATA_ENTRIES.has(relativePath.split(/[\\/]/)[0]);
}

async function verifyRestoredFiles(referenceDir: string, targetDir: string): Promise<void> {
  let entries;
  try {
    entries = await readdir(referenceDir, { recursive: true, withFileTypes: true });
  } catch (error) {
    throw new Error(`校验还原结果失败：${error instanceof Error ? error.message : String(error)}`);
  }
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const sourcePath = path.join(entry.parentPath, entry.name);
    const relativePath = path.relative(referenceDir, sourcePath);
    if (!isCoreDataPath(relativePath)) continue;
    const targetPath = path.join(targetDir, relativePath);
    let targetStat;
    try {
      targetStat = await stat(targetPath);
    } catch {
      throw new Error(`还原校验失败：缺少文件 ${relativePath}`);
    }
    let expectedSize: number;
    try {
      expectedSize = (await stat(sourcePath)).size;
    } catch (error) {
      throw new Error(`还原校验失败：无法读取备份文件 ${relativePath}：${error instanceof Error ? error.message : String(error)}`);
    }
    if (targetStat.size !== expectedSize) {
      throw new Error(`还原校验失败：文件大小不一致 ${relativePath}（期望 ${expectedSize}，实际 ${targetStat.size}）`);
    }
    let expectedHash: string;
    try {
      expectedHash = await hashFile(sourcePath);
    } catch (error) {
      throw new Error(`还原校验失败：无法读取备份文件 ${relativePath}：${error instanceof Error ? error.message : String(error)}`);
    }
    if ((await hashFile(targetPath)) !== expectedHash) {
      throw new Error(`还原校验失败：文件内容与备份不符 ${relativePath}`);
    }
  }
}
