import path from "node:path";
import type { StoredDesktopConfig, StoredDesktopInstance } from "./config.js";

export function normalizeInstallDir(installDir: string): string {
  const resolved = path.resolve(installDir);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

export function findLocalInstanceByInstallDir(config: StoredDesktopConfig | null, installDir: string): StoredDesktopInstance | null {
  if (!config) return null;
  const normalizedInstallDir = normalizeInstallDir(installDir);
  return (
    config.instances.find(
      (instance) =>
        instance.mode === "local" && instance.installDir !== null && normalizeInstallDir(instance.installDir) === normalizedInstallDir,
    ) ?? null
  );
}
