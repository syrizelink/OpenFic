import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";

export const BACKUP_MANIFEST_NAME = ".openfic-manifest.json";
const BACKUP_MANIFEST_VERSION = 1;

export interface BackupManifestEntry {
  size: number;
  sha256: string;
}

export interface BackupManifest {
  version: number;
  createdAt: string;
  entries: Record<string, BackupManifestEntry>;
}

export async function hashFile(filePath: string): Promise<string> {
  const hash = createHash("sha256");
  await pipeline(createReadStream(filePath), hash);
  return hash.digest("hex");
}

export async function computeBackupManifest(dir: string): Promise<BackupManifest> {
  const entries: Record<string, BackupManifestEntry> = {};
  const files = await readdir(dir, { recursive: true, withFileTypes: true });
  for (const entry of files) {
    if (!entry.isFile()) continue;
    const fullPath = path.join(entry.parentPath, entry.name);
    const name = path.relative(dir, fullPath).split(path.sep).join("/");
    if (name === BACKUP_MANIFEST_NAME) continue;
    entries[name] = {
      size: (await stat(fullPath)).size,
      sha256: await hashFile(fullPath),
    };
  }
  return { version: BACKUP_MANIFEST_VERSION, createdAt: new Date().toISOString(), entries };
}

export async function verifyBackupManifest(dir: string): Promise<void> {
  let manifest: BackupManifest;
  try {
    manifest = JSON.parse(await readFile(path.join(dir, BACKUP_MANIFEST_NAME), "utf8")) as BackupManifest;
  } catch {
    throw new Error(`备份缺少有效清单（${BACKUP_MANIFEST_NAME}），可能不是 OpenFic 备份或文件已损坏`);
  }
  if (manifest.version !== BACKUP_MANIFEST_VERSION || typeof manifest.entries !== "object" || manifest.entries === null) {
    throw new Error(`备份清单版本不受支持（${BACKUP_MANIFEST_NAME}）`);
  }

  const actualFiles = new Map<string, number>();
  const files = await readdir(dir, { recursive: true, withFileTypes: true });
  for (const entry of files) {
    if (!entry.isFile()) continue;
    const fullPath = path.join(entry.parentPath, entry.name);
    const name = path.relative(dir, fullPath).split(path.sep).join("/");
    if (name === BACKUP_MANIFEST_NAME) continue;
    actualFiles.set(name, (await stat(fullPath)).size);
  }

  for (const [name, expected] of Object.entries(manifest.entries)) {
    const actualSize = actualFiles.get(name);
    if (actualSize === undefined) throw new Error(`备份校验失败：缺少文件 ${name}`);
    if (actualSize !== expected.size) throw new Error(`备份校验失败：文件大小不一致 ${name}`);
  }
  for (const [name, actualSize] of actualFiles) {
    const expected = manifest.entries[name];
    if (!expected) throw new Error(`备份校验失败：存在清单外文件 ${name}`);
    if (actualSize !== expected.size) throw new Error(`备份校验失败：文件大小不一致 ${name}`);
  }
  for (const name of Object.keys(manifest.entries)) {
    if ((await hashFile(path.join(dir, name))) !== manifest.entries[name].sha256) {
      throw new Error(`备份校验失败：文件内容与清单不符 ${name}`);
    }
  }
}
