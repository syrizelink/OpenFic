import { app } from "electron";
import path from "node:path";
import type { DesktopInstance } from "../shared/config.js";

export function getDefaultDataDir(): string {
  return app.getPath("userData");
}

export function resolveDataDir(instance: DesktopInstance): string {
  return instance.dataDir ?? getDefaultDataDir();
}

export function normalizeDataDir(dataDir: string | null | undefined): string | null {
  if (!dataDir) return null;
  const defaultDir = path.resolve(getDefaultDataDir());
  const resolved = path.resolve(dataDir);
  const same =
    process.platform === "win32"
      ? resolved.toLowerCase() === defaultDir.toLowerCase()
      : resolved === defaultDir;
  return same ? null : resolved;
}
