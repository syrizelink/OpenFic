import { createReadStream, createWriteStream } from "node:fs";
import type { Dirent } from "node:fs";
import { mkdir, mkdtemp, readdir, realpath, rename, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { createGzip } from "node:zlib";
import { pack } from "tar-stream";
import { BACKUP_MANIFEST_NAME, computeBackupManifest } from "./backup-manifest.js";
import {
  assertDirNoSymlink,
  copyTree,
  copyWithRetry,
  CORE_DATA_ENTRIES,
  extractTarGz,
  isExcludedRuntimeEntry,
  measureTreeSize,
  type DataPhaseReporter,
} from "./runtime/tar-extract.js";

export interface DataDirInspection {
  valid: boolean;
  hasData: boolean;
  entryCount: number;
  sizeBytes: number;
}

async function pathExists(filePath: string): Promise<boolean> {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

interface WalkSummary {
  entryCount: number;
  sizeBytes: number;
  hasDatabase: boolean;
  hasCoversDir: boolean;
  hasKeyFile: boolean;
}

async function summarizeDirectory(dir: string): Promise<WalkSummary> {
  const summary: WalkSummary = { entryCount: 0, sizeBytes: 0, hasDatabase: false, hasCoversDir: false, hasKeyFile: false };
  const root = path.resolve(dir);
  if (!(await pathExists(root))) return summary;

  const entries = await readdir(root, { recursive: true, withFileTypes: true });
  for (const entry of entries) {
    if (isExcludedRuntimeEntry(entry.name)) continue;
    if (entry.isSymbolicLink()) continue;
    const fullPath = path.join(entry.parentPath, entry.name);
    if (entry.isFile()) {
      summary.entryCount += 1;
      try {
        summary.sizeBytes += (await stat(fullPath)).size;
      } catch {
        // Ignore transient stat failures when estimating size.
      }
      if (entry.name === "openfic.db") summary.hasDatabase = true;
      if (entry.name === ".key") summary.hasKeyFile = true;
      continue;
    }
    if (entry.isDirectory() && entry.name === "covers") summary.hasCoversDir = true;
  }
  return summary;
}

export async function inspectDataDir(dataDir: string): Promise<DataDirInspection> {
  const summary = await summarizeDirectory(dataDir);
  return {
    valid: summary.hasDatabase || summary.hasCoversDir || summary.hasKeyFile,
    hasData: summary.entryCount > 0,
    entryCount: summary.entryCount,
    sizeBytes: summary.sizeBytes,
  };
}

async function addDirectoryToPack(
  archive: ReturnType<typeof pack>,
  directory: string,
  baseDir: string,
): Promise<void> {
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    const archiveName = path.relative(baseDir, fullPath).split(path.sep).join("/");
    if (entry.isDirectory()) {
      archive.entry({ name: `${archiveName}/`, type: "directory" });
      await addDirectoryToPack(archive, fullPath, baseDir);
      continue;
    }
    if (entry.isFile()) {
      const size = (await stat(fullPath)).size;
      const writable = archive.entry({ name: archiveName, size });
      await pipeline(createReadStream(fullPath), writable);
      continue;
    }
  }
}

export async function backupDataDir(
  dataDir: string,
  targetPath: string,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
): Promise<void> {
  await mkdir(path.dirname(targetPath), { recursive: true });
  const stagingDir = await mkdtemp(path.join(os.tmpdir(), "openfic-backup-"));
  const tmpPath = `${targetPath}.tmp`;
  try {
    await copyDirectoryWithRetry(dataDir, stagingDir, onLog, onPhase);
    await writeFile(path.join(stagingDir, BACKUP_MANIFEST_NAME), JSON.stringify(await computeBackupManifest(stagingDir), null, 2));
    onPhase?.("pack");
    const archive = pack();
    const output = createWriteStream(tmpPath);
    const done = pipeline(archive, createGzip(), output);
    await addDirectoryToPack(archive, stagingDir, stagingDir);
    archive.finalize();
    await done;
    await rename(tmpPath, targetPath);
  } finally {
    await rm(tmpPath, { force: true });
    await rm(stagingDir, { recursive: true, force: true });
  }
}

async function copyDirectoryWithRetry(
  sourceDir: string,
  targetDir: string,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
): Promise<void> {
  let entries: Dirent[];
  try {
    entries = await readdir(sourceDir, { withFileTypes: true });
  } catch (error) {
    throw new Error(`无法读取数据目录 ${sourceDir}：${error instanceof Error ? error.message : String(error)}`);
  }
  await assertDirNoSymlink(targetDir);
  let total = 0;
  const coreSizes = new Map<string, number>();
  const copyable: { name: string; core: boolean }[] = [];
  for (const entry of entries) {
    const name = entry.name;
    if (isExcludedRuntimeEntry(name)) continue;
    if (name === BACKUP_MANIFEST_NAME) continue;
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
      onPhase?.("copy", rounded / 100);
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
      });
    }
  }
  report();
}

export async function restoreDataDir(
  sourcePath: string,
  targetDir: string,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
): Promise<void> {
  await extractTarGz(sourcePath, targetDir, onLog, onPhase);
}

export async function migrateDataDir(
  fromDir: string,
  toDir: string,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
): Promise<void> {
  const resolvedFrom = await resolveForCompare(fromDir);
  const resolvedTo = await resolveForCompare(toDir);
  if (pathEquals(resolvedFrom, resolvedTo)) {
    throw new Error("迁移目标目录不能与源目录相同");
  }
  if (pathContains(resolvedFrom, resolvedTo)) {
    throw new Error("迁移目标目录不能位于源目录内部");
  }
  if (pathContains(resolvedTo, resolvedFrom)) {
    throw new Error("迁移源目录不能位于目标目录内部");
  }
  await mkdir(toDir, { recursive: true });
  try {
    await copyDirectoryWithRetry(fromDir, toDir, onLog, onPhase);
  } catch (error) {
    await rm(toDir, { recursive: true, force: true });
    throw error;
  }
}

function normalizeForCompare(filePath: string): string {
  const resolved = path.resolve(filePath);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

async function resolveForCompare(filePath: string): Promise<string> {
  try {
    return normalizeForCompare(await realpath(filePath));
  } catch {
    const missing: string[] = [];
    let current = filePath;
    while (true) {
      try {
        const real = await realpath(current);
        return normalizeForCompare(path.join(real, ...missing));
      } catch {
        const parent = path.dirname(current);
        if (parent === current) return normalizeForCompare(filePath);
        missing.unshift(path.basename(current));
        current = parent;
      }
    }
  }
}

function pathEquals(left: string, right: string): boolean {
  return normalizeForCompare(left) === normalizeForCompare(right);
}

function pathContains(parent: string, child: string): boolean {
  const relative = path.relative(normalizeForCompare(parent), normalizeForCompare(child));
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

export async function arePathsEqual(left: string, right: string): Promise<boolean> {
  return pathEquals(await resolveForCompare(left), await resolveForCompare(right));
}

export async function isPathWithin(parent: string, child: string): Promise<boolean> {
  return pathContains(await resolveForCompare(parent), await resolveForCompare(child));
}

export async function doPathsOverlap(left: string, right: string): Promise<boolean> {
  const resolvedLeft = await resolveForCompare(left);
  const resolvedRight = await resolveForCompare(right);
  return pathEquals(resolvedLeft, resolvedRight) || pathContains(resolvedLeft, resolvedRight) || pathContains(resolvedRight, resolvedLeft);
}

export async function removeDataDir(dataDir: string): Promise<void> {
  await rm(dataDir, { recursive: true, force: true });
}
