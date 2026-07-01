import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { defaultDesktopConfig, type DesktopConfig } from "../shared/config.js";

const electron = require("electron") as typeof import("electron");

const { app } = electron;

function getConfigPath(): string {
  return path.join(app.getPath("userData"), "config.json");
}

function isDesktopConfig(value: unknown): value is DesktopConfig {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DesktopConfig>;
  return (
    (candidate.mode === "local" || candidate.mode === "remote") &&
    (typeof candidate.remoteUrl === "string" || candidate.remoteUrl === null) &&
    typeof candidate.autoStartLocal === "boolean" &&
    (typeof candidate.installDir === "string" || candidate.installDir === null)
  );
}

export async function readDesktopConfig(): Promise<DesktopConfig | null> {
  try {
    const raw = await readFile(getConfigPath(), "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    if (!isDesktopConfig(parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export async function writeDesktopConfig(config: DesktopConfig): Promise<void> {
  const configPath = getConfigPath();
  await mkdir(path.dirname(configPath), { recursive: true });
  await writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf-8");
}

export function createDefaultConfig(): DesktopConfig {
  return { ...defaultDesktopConfig };
}
