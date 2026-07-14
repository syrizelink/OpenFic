import { app } from "electron";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { defaultDesktopConfig, type DesktopConfig, type DesktopInstance } from "../shared/config.js";

function getConfigPath(): string {
  return path.join(app.getPath("userData"), "config.json");
}

function isDesktopInstance(value: unknown): value is DesktopInstance {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DesktopInstance>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.name === "string" &&
    (candidate.mode === "local" || candidate.mode === "remote") &&
    (typeof candidate.remoteUrl === "string" || candidate.remoteUrl === null) &&
    typeof candidate.autoStartLocal === "boolean" &&
    (typeof candidate.installDir === "string" || candidate.installDir === null)
  );
}

function isDesktopConfig(value: unknown): value is DesktopConfig {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DesktopConfig>;
  return (
    (typeof candidate.activeInstanceId === "string" || candidate.activeInstanceId === null) &&
    Array.isArray(candidate.instances) &&
    candidate.instances.every(isDesktopInstance)
  );
}

function isLegacyDesktopConfig(value: unknown): value is Omit<DesktopInstance, "id" | "name"> {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Omit<DesktopInstance, "id" | "name">>;
  return (
    (candidate.mode === "local" || candidate.mode === "remote") &&
    (typeof candidate.remoteUrl === "string" || candidate.remoteUrl === null) &&
    typeof candidate.autoStartLocal === "boolean" &&
    (typeof candidate.installDir === "string" || candidate.installDir === null) &&
    (candidate.favorite === undefined || typeof candidate.favorite === "boolean")
  );
}

function createInstanceId(): string {
  return `instance-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function getInstanceName(instance: Omit<DesktopInstance, "id" | "name">): string {
  if (instance.mode === "local") return "Local";
  try {
    return new URL(instance.remoteUrl ?? "").host || "Remote";
  } catch {
    return instance.remoteUrl || "Remote";
  }
}

function migrateLegacyConfig(config: Omit<DesktopInstance, "id" | "name">): DesktopConfig {
  const instance: DesktopInstance = {
    id: createInstanceId(),
    name: getInstanceName(config),
    ...config,
  };
  return {
    activeInstanceId: instance.id,
    instances: [instance],
  };
}

export async function readDesktopConfig(): Promise<DesktopConfig | null> {
  try {
    const raw = await readFile(getConfigPath(), "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    if (isDesktopConfig(parsed)) return parsed;
    if (!isLegacyDesktopConfig(parsed)) return null;
    const migrated = migrateLegacyConfig(parsed);
    await writeDesktopConfig(migrated);
    return migrated;
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
