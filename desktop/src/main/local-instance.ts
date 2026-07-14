import path from "node:path";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

export function normalizeInstallDir(installDir: string): string {
  const resolved = path.resolve(installDir);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

export function findLocalInstanceByInstallDir(config: DesktopConfig | null, installDir: string): DesktopInstance | null {
  if (!config) return null;
  const normalizedInstallDir = normalizeInstallDir(installDir);
  return (
    config.instances.find(
      (instance) =>
        instance.mode === "local" &&
        instance.installDir !== null &&
        normalizeInstallDir(instance.installDir) === normalizedInstallDir,
    ) ?? null
  );
}
