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
    throw new Error(`Cadangan tidak memiliki manifes yang valid (${BACKUP_MANIFEST_NAME}); mungkin bukan cadangan OpenFic atau berkasnya rusak`);
  }
  if (manifest.version !== BACKUP_MANIFEST_VERSION || typeof manifest.entries !== "object" || manifest.entries === null) {
    throw new Error(`Versi manifes cadangan tidak didukung (${BACKUP_MANIFEST_NAME})`);
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
    if (actualSize === undefined) throw new Error(`Verifikasi cadangan gagal: berkas ${name} tidak ada`);
    if (actualSize !== expected.size) throw new Error(`Verifikasi cadangan gagal: ukuran berkas tidak konsisten ${name}`);
  }
  for (const [name, actualSize] of actualFiles) {
    const expected = manifest.entries[name];
    if (!expected) throw new Error(`Verifikasi cadangan gagal: ada berkas di luar manifes ${name}`);
    if (actualSize !== expected.size) throw new Error(`Verifikasi cadangan gagal: ukuran berkas tidak konsisten ${name}`);
  }
  for (const name of Object.keys(manifest.entries)) {
    if ((await hashFile(path.join(dir, name))) !== manifest.entries[name].sha256) {
      throw new Error(`Verifikasi cadangan gagal: isi berkas tidak sesuai dengan manifes ${name}`);
    }
  }
}
