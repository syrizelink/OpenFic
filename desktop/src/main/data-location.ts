import { app } from "electron";
import type { DesktopInstance } from "../shared/config.js";

export function getDefaultDataDir(): string {
  return app.getPath("userData");
}

export function resolveDataDir(instance: DesktopInstance): string {
  return instance.dataDir ?? getDefaultDataDir();
}