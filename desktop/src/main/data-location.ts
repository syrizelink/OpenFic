import { app } from "electron";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

export function getDefaultDataDir(): string {
  return app.getPath("userData");
}

export function resolveDataDir(instance: DesktopInstance): string {
  return instance.dataDir ?? getDefaultDataDir();
}

const CONFIG_FILE_NAME = "config.json";

/**
 * 同步解析当前活动实例的数据目录，用于 app ready 之前
 * 重定向 session 数据（localStorage/cache）落盘位置。
 * 无法读取配置或活动实例未自定义数据目录时返回 null。
 */
export function resolveActiveSessionDataDir(): string | null {
  try {
    const configPath = path.join(app.getPath("userData"), CONFIG_FILE_NAME);
    if (!existsSync(configPath)) return null;
    const raw = readFileSync(configPath, "utf-8");
    const parsed = JSON.parse(raw) as Partial<DesktopConfig> | null;
    if (!parsed || typeof parsed !== "object") return null;
    const instances = Array.isArray(parsed.instances) ? parsed.instances : [];
    const activeId = typeof parsed.activeInstanceId === "string" ? parsed.activeInstanceId : null;
    const instance = instances.find(
      (candidate) => (activeId ? candidate.id === activeId : true),
    ) as Partial<DesktopInstance> | undefined;
    if (!instance || instance.mode !== "local") return null;
    if (typeof instance.dataDir !== "string" || !instance.dataDir) return null;
    return instance.dataDir;
  } catch {
    return null;
  }
}