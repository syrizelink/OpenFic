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

async function extractWithSystemTar(archivePath: string, outputDir: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const child = spawn("tar", ["-xzf", archivePath, "-C", outputDir], {
      windowsHide: true,
      stdio: ["ignore", "ignore", "inherit"],
    });
    child.once("error", reject);
    child.once("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`tar exited with code ${code}`));
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

export async function extractTarGz(archivePath: string, outputDir: string): Promise<void> {
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });

  try {
    await extractWithSystemTar(archivePath, outputDir);
  } catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
    await rm(outputDir, { recursive: true, force: true });
    await mkdir(outputDir, { recursive: true });
    await extractWithBuiltInTar(archivePath, outputDir);
  }
}
