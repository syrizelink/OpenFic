import type { BrowserWindow } from "electron";
import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { registerAppScheme, handleAppProtocol, setRuntimeConfig } from "./protocol.js";
import { createMainWindow } from "./windows.js";
import { readDesktopConfig, writeDesktopConfig } from "./config.js";
import { registerIpc } from "./ipc.js";
import { waitForBackend } from "./health.js";
import { ensurePortablePython, resolveRuntimeDir } from "./runtime/python.js";
import { ensureOpenFicRuntime, startLocalOpenFicBackend } from "./runtime/openfic.js";
import { stopBackendProcess, type BackendProcessHandle } from "./process.js";
import type { InitializeAppResult } from "../shared/ipc.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

const electron = require("electron") as typeof import("electron");

const { app, dialog, Menu } = electron;

function writeStartupLog(message: string): void {
  try {
    const logDir = path.join(process.env.APPDATA ?? app.getPath("userData"), "OpenFic");
    mkdirSync(logDir, { recursive: true });
    appendFileSync(path.join(logDir, "startup.log"), `[${new Date().toISOString()}] ${message}\n`, "utf8");
  } catch {
    // Ignore logging failures during startup diagnostics.
  }
}

let mainWindow: BrowserWindow | null = null;
let backendHandle: BackendProcessHandle | null = null;
let activeInstanceId: string | null = null;
let isQuitting = false;

writeStartupLog("process start");
registerAppScheme();
writeStartupLog("scheme registered");

function setBackend(handle: BackendProcessHandle): void {
  const previousHandle = backendHandle;
  backendHandle = handle;
  backendHandle.process.on("exit", () => {
    const wasActiveHandle = backendHandle === handle;
    if (wasActiveHandle) backendHandle = null;
    if (!isQuitting && wasActiveHandle) {
      dialog.showErrorBox("OpenFic 后端已退出", `后端服务异常退出。日志路径：${handle.logPath}`);
      app.quit();
    }
  });
  if (previousHandle && previousHandle !== handle) stopBackendProcess(previousHandle);
}

function clearBackend(): void {
  const previousHandle = backendHandle;
  backendHandle = null;
  if (previousHandle) stopBackendProcess(previousHandle);
}

function setBackendBaseUrl(url: string): void {
  setRuntimeConfig({ backendBaseUrl: url.replace(/\/+$/, "") });
}

function onConfigSaved(config: DesktopConfig): void {
  activeInstanceId = config.activeInstanceId;
}

function attachWindowLifecycle(window: BrowserWindow): void {
  window.on("closed", () => {
    if (mainWindow === window) mainWindow = null;
  });
}

function openMainWindow(): void {
  const existingWindow = mainWindow;
  if (existingWindow) {
    existingWindow.focus();
    return;
  }
  mainWindow = createMainWindow();
  attachWindowLifecycle(mainWindow);
}

async function startLocalBackend(installDir: string | null): Promise<void> {
  const runtimeDir = resolveRuntimeDir(installDir);
  const python = await ensurePortablePython(runtimeDir, () => undefined, () => undefined);
  const runtime = await ensureOpenFicRuntime(python, runtimeDir, () => undefined);
  const backend = await startLocalOpenFicBackend(runtime.venvPythonPath);
  setBackend(backend);
  setBackendBaseUrl(backend.baseUrl);
}

function getActiveInstance(config: DesktopConfig): DesktopInstance | null {
  return config.instances.find((instance) => instance.id === config.activeInstanceId) ?? config.instances[0] ?? null;
}

async function activateInstance(config: DesktopConfig, instance: DesktopInstance): Promise<void> {
  activeInstanceId = instance.id;
  if (instance.mode === "remote") {
    if (!instance.remoteUrl) throw new Error("远程实例缺少后端地址");
    await waitForBackend(instance.remoteUrl, 10_000);
    clearBackend();
    setBackendBaseUrl(instance.remoteUrl);
    return;
  }

  await startLocalBackend(instance.installDir);
}

async function switchInstance(instanceId: string): Promise<InitializeAppResult> {
  const config = await readDesktopConfig();
  if (!config) return { status: "needs-setup" };
  const instance = config.instances.find((item) => item.id === instanceId);
  if (!instance) throw new Error("实例不存在");

  await activateInstance(config, instance);
  await writeDesktopConfig({ ...config, activeInstanceId: instance.id });
  return { status: "ready", activeInstanceId: instance.id };
}

async function pingInstance(instance: DesktopInstance): Promise<number> {
  const startedAt = performance.now();
  if (instance.mode === "local") {
    if (instance.id !== activeInstanceId || !backendHandle) throw new Error("本地实例尚未启动");
    await waitForBackend(backendHandle.baseUrl, 10_000);
    return Math.round(performance.now() - startedAt);
  }

  if (!instance.remoteUrl) throw new Error("远程实例缺少后端地址");
  await waitForBackend(instance.remoteUrl, 10_000);
  return Math.round(performance.now() - startedAt);
}

function installMenu(): void {
  Menu.setApplicationMenu(null);
}

async function initializeApp(): Promise<InitializeAppResult> {
  const config = await readDesktopConfig();
  writeStartupLog(`config loaded: ${config ? `${config.instances.length} instances` : "none"}`);

  if (!config || config.instances.length === 0) {
    return { status: "needs-setup" };
  }

  const instance = getActiveInstance(config);
  if (!instance) return { status: "needs-setup" };

  try {
    await activateInstance(config, instance);
    if (config.activeInstanceId !== instance.id) {
      await writeDesktopConfig({ ...config, activeInstanceId: instance.id });
    }
    return { status: "ready", activeInstanceId: instance.id };
  } catch (err) {
    writeStartupLog(`backend failed: ${err instanceof Error ? err.message : String(err)}`);
    return {
      status: "needs-setup",
      activeInstanceId: instance.id,
      message: err instanceof Error ? err.message : String(err),
    };
  }
}

async function bootstrap(): Promise<void> {
  writeStartupLog("bootstrap start");
  handleAppProtocol();
  writeStartupLog("protocol handler installed");
  installMenu();
  writeStartupLog("menu installed");
  registerIpc({
    shellWindow: () => mainWindow,
    setBackend,
    setBackendBaseUrl,
    initializeApp,
    switchInstance,
    pingInstance,
    onConfigSaved,
  });

  writeStartupLog("opening shell window");
  openMainWindow();
}

const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    writeStartupLog("app ready");
    void bootstrap();
  });

  app.on("window-all-closed", () => {
    app.quit();
  });

  app.on("before-quit", () => {
    isQuitting = true;
    stopBackendProcess(backendHandle);
  });

  process.on("exit", () => stopBackendProcess(backendHandle));
  process.on("SIGINT", () => {
    stopBackendProcess(backendHandle);
    process.exit(0);
  });
  process.on("SIGTERM", () => {
    stopBackendProcess(backendHandle);
    process.exit(0);
  });

  process.on("uncaughtException", (error) => {
    writeStartupLog(`uncaughtException: ${error.stack ?? error.message}`);
    throw error;
  });

  process.on("unhandledRejection", (reason) => {
    writeStartupLog(`unhandledRejection: ${reason instanceof Error ? reason.stack ?? reason.message : String(reason)}`);
  });
}
