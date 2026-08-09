import { createReadStream, createWriteStream } from "node:fs";
import { cp, mkdir, readdir, readlink, rm, stat } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { createGzip } from "node:zlib";
import { pack } from "tar-stream";
import { extractTarGz } from "./runtime/tar-extract.js";

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

export async function backupDataDir(dataDir: string, targetPath: string): Promise<void> {
  await mkdir(path.dirname(targetPath), { recursive: true });
  const archive = pack();
  const output = createWriteStream(targetPath);
  const done = pipeline(archive, createGzip(), output);
  await addDirectoryToPack(archive, dataDir, dataDir);
  archive.finalize();
  await done;
}

export async function restoreDataDir(sourcePath: string, targetDir: string): Promise<void> {
  await extractTarGz(sourcePath, targetDir);
}

export async function migrateDataDir(fromDir: string, toDir: string): Promise<void> {
  await mkdir(toDir, { recursive: true });
  try {
    await cp(fromDir, toDir, { recursive: true });
  } catch (error) {
    await rm(toDir, { recursive: true, force: true });
    throw error;
  }
}

export async function removeDataDir(dataDir: string): Promise<void> {
  await rm(dataDir, { recursive: true, force: true });
}