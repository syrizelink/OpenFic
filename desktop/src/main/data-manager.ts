import { createReadStream, createWriteStream } from "node:fs";
import { cp, mkdir, mkdtemp, readdir, readlink, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { createGzip } from "node:zlib";
import { pack } from "tar-stream";
import { BACKUP_MANIFEST_NAME, computeBackupManifest } from "./backup-manifest.js";
import { copyTree, extractTarGz, isExcludedRuntimeEntry, measureTreeSize, type DataPhaseReporter } from "./runtime/tar-extract.js";

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
    if (entry.isSymbolicLink()) {
      archive.entry({ name: archiveName, type: "symlink", linkname: await readlink(fullPath) });
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
  try {
    await copyDirectoryWithRetry(dataDir, stagingDir, onLog, onPhase);
    await writeFile(path.join(stagingDir, BACKUP_MANIFEST_NAME), JSON.stringify(await computeBackupManifest(stagingDir), null, 2));
    onPhase?.("pack");
    const archive = pack();
    const output = createWriteStream(targetPath);
    const done = pipeline(archive, createGzip(), output);
    await addDirectoryToPack(archive, stagingDir, stagingDir);
    archive.finalize();
    await done;
  } finally {
    await rm(stagingDir, { recursive: true, force: true });
  }
}

const BACKUP_RETRY_ATTEMPTS = 5;
const BACKUP_RETRY_BASE_DELAY_MS = 250;
const CORE_DATA_ENTRIES = new Set(["openfic.db", ".key", "covers"]);

function isRetryableBackupError(error: unknown): boolean {
  const code = (error as NodeJS.ErrnoException).code;
  return code === "EBUSY" || code === "EPERM" || code === "EACCES";
}

async function copyWithRetry(sourcePath: string, targetPath: string): Promise<void> {
  for (let attempt = 1; ; attempt++) {
    try {
      await cp(sourcePath, targetPath, { recursive: true });
      return;
    } catch (error) {
      await rm(targetPath, { recursive: true, force: true });
      if (attempt >= BACKUP_RETRY_ATTEMPTS || !isRetryableBackupError(error)) throw error;
      await new Promise((resolve) => setTimeout(resolve, BACKUP_RETRY_BASE_DELAY_MS * attempt));
    }
  }
}

async function copyDirectoryWithRetry(
  sourceDir: string,
  targetDir: string,
  onLog?: (message: string) => void,
  onPhase?: DataPhaseReporter,
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
  await mkdir(toDir, { recursive: true });
  try {
    await copyDirectoryWithRetry(fromDir, toDir, onLog, onPhase);
  } catch (error) {
    await rm(toDir, { recursive: true, force: true });
    throw error;
  }
}

export async function removeDataDir(dataDir: string): Promise<void> {
  await rm(dataDir, { recursive: true, force: true });
}