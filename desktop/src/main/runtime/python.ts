import { app } from "electron";
import { access, mkdir } from "node:fs/promises";
import path from "node:path";
import { downloadFile, extractTarGz } from "./archive.js";
import { resolvePythonAsset } from "./python-assets.js";

export interface PortablePython {
  pythonPath: string;
  rootDir: string;
}

export function getRuntimeDir(): string {
  return path.join(app.getPath("userData"), "runtime");
}

export function getPortablePythonRoot(): string {
  return path.join(getRuntimeDir(), "python");
}

export function getPortablePythonPath(rootDir = getPortablePythonRoot()): string {
  if (process.platform === "win32") return path.join(rootDir, "python", "python.exe");
  return path.join(rootDir, "python", "install", "bin", "python3");
}

async function pathExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function ensurePortablePython(onProgress: (message: string) => void): Promise<PortablePython> {
  const rootDir = getPortablePythonRoot();
  const pythonPath = getPortablePythonPath(rootDir);
  if (await pathExists(pythonPath)) return { pythonPath, rootDir };

  const asset = resolvePythonAsset();
  const archivePath = path.join(getRuntimeDir(), `python-${asset.version}-${asset.target}.tar.gz`);
  await mkdir(getRuntimeDir(), { recursive: true });

  onProgress(`下载 Python ${asset.version}`);
  await downloadFile(asset.url, archivePath);

  onProgress("解压 Python");
  await extractTarGz(archivePath, rootDir);

  if (!(await pathExists(pythonPath))) {
    throw new Error(`portable Python not found after extraction: ${pythonPath}`);
  }

  return { pythonPath, rootDir };
}
