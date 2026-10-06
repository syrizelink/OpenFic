import { app } from "electron";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { isDesktopInstanceAppearance, type DesktopInstance, type DesktopInstanceAppearance } from "../../shared/config.js";
import { findFreePort } from "../ports.js";
import { startBackendProcess, type BackendProcessHandle } from "../process.js";
import { throwIfAborted, waitForBackend } from "../health.js";
import type { StartupProgressTracker } from "../startup-progress.js";
import { appendLog } from "../logging.js";

const DEV_BACKEND_CONNECT_TIMEOUT_MS = 10_000;
const DEV_BACKEND_SPAWN_TIMEOUT_MS = 120_000;

export const DEV_INSTANCE_ID = "instance-dev-local";

export function isDevMode(): boolean {
  return !app.isPackaged && process.env.OPENFIC_DEV_MODE === "1";
}

export function getDevBackendUrl(): string | null {
  const url = process.env.OPENFIC_DEV_BACKEND_URL;
  return url ? url.replace(/\/+$/, "") : null;
}

export function getDevDataDir(): string {
  const override = process.env.OPENFIC_DEV_DATA_DIR;
  if (override) return path.resolve(override);
  return path.join(app.getAppPath(), "..", "tmp", "dev-data");
}

function getDevStatePath(): string {
  return path.join(app.getAppPath(), "..", "tmp", "dev-instance.json");
}

interface DevInstanceState {
  dataDir?: unknown;
  appearance?: unknown;
  fontFamily?: unknown;
  codeFontFamily?: unknown;
  themeVariables?: unknown;
}

async function readDevInstanceState(): Promise<DevInstanceState> {
  try {
    const raw = await readFile(getDevStatePath(), "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed as DevInstanceState;
  } catch {
    // 状态文件不存在或损坏时回退到默认配置
  }
  return {};
}

async function writeDevInstanceState(state: DevInstanceState): Promise<void> {
  await mkdir(path.dirname(getDevStatePath()), { recursive: true });
  await writeFile(getDevStatePath(), `${JSON.stringify(state, null, 2)}\n`, "utf-8");
}

export async function readDevInstanceDataDir(): Promise<string> {
  const override = process.env.OPENFIC_DEV_DATA_DIR;
  if (override) return path.resolve(override);
  const state = await readDevInstanceState();
  if (typeof state.dataDir === "string" && state.dataDir) return state.dataDir;
  return getDevDataDir();
}

export async function readDevInstanceAppearance(): Promise<DesktopInstanceAppearance> {
  const state = await readDevInstanceState();
  const appearance = {
    appearance: state.appearance,
    fontFamily: state.fontFamily,
    codeFontFamily: state.codeFontFamily,
    themeVariables: state.themeVariables,
  };
  return isDesktopInstanceAppearance(appearance) ? appearance : {};
}

export function isDevInstance(instance: DesktopInstance): boolean {
  return instance.id === DEV_INSTANCE_ID;
}

export async function createDevInstance(): Promise<DesktopInstance> {
  return {
    id: DEV_INSTANCE_ID,
    name: "Dev",
    mode: "local",
    remoteUrl: null,
    autoStartLocal: true,
    installDir: path.join(app.getAppPath(), "..", "backend"),
    dataDir: await readDevInstanceDataDir(),
    ...(await readDevInstanceAppearance()),
  };
}

export async function persistDevInstanceDataDir(dataDir: string): Promise<void> {
  const state = await readDevInstanceState();
  await writeDevInstanceState({ ...state, dataDir });
}

export async function persistDevInstanceAppearance(appearance: DesktopInstanceAppearance): Promise<void> {
  const currentAppearance = await readDevInstanceAppearance();
  const nextAppearance: DesktopInstanceAppearance = {
    ...currentAppearance,
    ...(appearance.appearance === undefined ? {} : { appearance: appearance.appearance }),
    ...(appearance.fontFamily === undefined ? {} : { fontFamily: appearance.fontFamily }),
    ...(appearance.codeFontFamily === undefined ? {} : { codeFontFamily: appearance.codeFontFamily }),
    ...(appearance.themeVariables === undefined ? {} : { themeVariables: appearance.themeVariables }),
  };
  const state = await readDevInstanceState();
  await writeDevInstanceState({
    ...state,
    ...(nextAppearance.appearance === undefined ? {} : { appearance: nextAppearance.appearance }),
    ...(nextAppearance.fontFamily === undefined ? {} : { fontFamily: nextAppearance.fontFamily }),
    ...(nextAppearance.codeFontFamily === undefined ? {} : { codeFontFamily: nextAppearance.codeFontFamily }),
    ...(nextAppearance.themeVariables === undefined ? {} : { themeVariables: nextAppearance.themeVariables }),
  });
}

export interface DevBackendResult {
  handle: BackendProcessHandle | null;
  baseUrl: string;
  maintenanceError: string | null;
}

async function fetchBackendMaintenanceError(baseUrl: string): Promise<string | null> {
  try {
    const response = await fetch(`${baseUrl}/api/v1/health/maintenance`);
    if (!response.ok) return null;
    const data = (await response.json()) as { status?: string; error?: string | null };
    if (data.status !== "failed") return null;
    return data.error || "本地数据库维护失败";
  } catch {
    return null;
  }
}

export async function startDevBackend(
  startupProgress: StartupProgressTracker,
  signal: AbortSignal,
): Promise<DevBackendResult> {
  throwIfAborted(signal);
  const externalUrl = getDevBackendUrl();
  if (externalUrl) {
    startupProgress.begin({
      step: "connect-remote",
      title: "连接开发后端",
      message: `正在连接 ${externalUrl}`,
      progress: 0.3,
    });
    await waitForBackend(externalUrl, { timeoutMs: DEV_BACKEND_CONNECT_TIMEOUT_MS, signal });
    throwIfAborted(signal);
    appendLog("backend", `开发模式已连接外部后端：${externalUrl}`);
    const maintenanceError = await fetchBackendMaintenanceError(externalUrl);
    return { handle: null, baseUrl: externalUrl, maintenanceError };
  }

  const devDataDir = getDevDataDir();
  await mkdir(devDataDir, { recursive: true });
  throwIfAborted(signal);
  startupProgress.begin({
    step: "start-backend",
    title: "启动开发后端",
    message: "正在从 backend 源码启动本地服务",
    progress: 0.3,
  });
  const port = await findFreePort();
  throwIfAborted(signal);
  const backendDir = path.join(app.getAppPath(), "..", "backend");
  const args = [
    "run",
    "--directory",
    backendDir,
    "uvicorn",
    "app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
  ];
  if (process.platform === "win32") args.push("--loop", "app.cli:_windows_selector_loop_factory");

  const handle = startBackendProcess({ command: "uv", args, port, dataDir: devDataDir });
  try {
    await waitForBackend(handle.baseUrl, {
      process: handle.process,
      signal,
      timeoutMs: DEV_BACKEND_SPAWN_TIMEOUT_MS,
    });
    throwIfAborted(signal);
    const maintenanceError = await fetchBackendMaintenanceError(handle.baseUrl);
    return { handle, baseUrl: handle.baseUrl, maintenanceError };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${message}。日志路径：${handle.logPath}`);
  }
}
