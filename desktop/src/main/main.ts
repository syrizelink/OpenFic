import { app, dialog, Menu, type BrowserWindow } from "electron";
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
import { initializeUpdater } from "./updater.js";
import { configureDefaultSystemProxy } from "./proxy.js";
import { createStartupProgressTracker, type StartupProgressTracker } from "./startup-progress.js";
import { IpcChannels } from "../shared/ipc.js";
import type { InitializeAppResult } from "../shared/ipc.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

function writeStartupLog(message: string): void {
  try {
    const logDir = path.join(process.env.APPDATA ?? app.getPath("userData"), "openfic-desktop");
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

function createStartupProgress(): StartupProgressTracker {
  return createStartupProgressTracker((progress) => {
    mainWindow?.webContents.send(IpcChannels.startupProgress, progress);
  });
}

async function startLocalBackend(installDir: string | null, startupProgress: StartupProgressTracker): Promise<void> {
  const runtimeDir = resolveRuntimeDir(installDir);
  startupProgress.begin({
    step: "check-runtime",
    title: "检查运行环境",
    message: "正在检查 Python 与 OpenFic 运行环境",
    progress: 0.15,
  });
  let pythonWasUpdated = false;
  const python = await ensurePortablePython(
    runtimeDir,
    (phase, message) => {
      pythonWasUpdated = true;
      startupProgress.begin({
        step: "update-python",
        title: phase === "download" ? "更新 Python 运行环境" : "修复 Python 运行环境",
        message,
        progress: phase === "download" ? 0.22 : 0.32,
      });
    },
    ({ received, total }) => {
      const fraction = total > 0 ? received / total : 0;
      startupProgress.update({
        step: "update-python",
        title: "更新 Python 运行环境",
        message: total > 0 ? `正在下载 Python · ${Math.round(fraction * 100)}%` : "正在下载 Python",
        progress: 0.22 + fraction * 0.1,
      });
    },
  );
  if (!pythonWasUpdated) {
    startupProgress.update({
      step: "check-runtime",
      title: "检查运行环境",
      message: "Python 运行环境已就绪",
      progress: 0.3,
    });
  }

  let runtimeWasUpdated = false;
  const runtime = await ensureOpenFicRuntime(python, runtimeDir, app.getVersion(), (step, message) => {
    runtimeWasUpdated = true;
    startupProgress.begin({
      step: "update-openfic",
      title: step === "install-openfic" ? "更新 OpenFic 后端" : "更新本地运行环境",
      message,
      progress: step === "install-openfic" ? 0.45 : 0.38,
    });
  });
  if (!runtimeWasUpdated) {
    startupProgress.update({
      step: "check-runtime",
      title: "检查运行环境",
      message: "运行环境已就绪",
      progress: 0.5,
    });
  }

  const backend = await startLocalOpenFicBackend(runtime.venvPythonPath, app.getVersion(), startupProgress);
  setBackend(backend);
  setBackendBaseUrl(backend.baseUrl);
}

function getActiveInstance(config: DesktopConfig): DesktopInstance | null {
  return config.instances.find((instance) => instance.id === config.activeInstanceId) ?? config.instances[0] ?? null;
}

async function activateInstance(
  config: DesktopConfig,
  instance: DesktopInstance,
  startupProgress: StartupProgressTracker,
): Promise<string | null> {
  activeInstanceId = instance.id;
  if (instance.mode === "remote") {
    if (!instance.remoteUrl) throw new Error("远程实例缺少后端地址");
    startupProgress.begin({
      step: "connect-remote",
      title: "连接 OpenFic 服务",
      message: `正在连接 ${instance.remoteUrl}`,
      progress: 0.3,
    });
    const health = await waitForBackend(instance.remoteUrl, 10_000);
    startupProgress.begin({
      step: "verify-remote",
      title: "验证服务状态",
      message: "远程服务已响应，正在验证版本",
      progress: 0.7,
    });
    clearBackend();
    setBackendBaseUrl(instance.remoteUrl);
    startupProgress.begin({
      step: "check-compatibility",
      title: "检查版本兼容性",
      message: "正在比较桌面端与后端版本",
      progress: 0.85,
    });
    if (health.version === app.getVersion()) return null;
    return `远程实例版本为 ${health.version ?? "未知"}，桌面端版本为 ${app.getVersion()}，部分功能可能不兼容。`;
  }

  await startLocalBackend(instance.installDir, startupProgress);
  return null;
}

async function switchInstance(instanceId: string): Promise<InitializeAppResult> {
  const startupProgress = createStartupProgress();
  startupProgress.begin({
    step: "load-config",
    title: "读取实例配置",
    message: "正在查找目标 OpenFic 实例",
    progress: 0.1,
  });
  try {
    const config = await readDesktopConfig();
    if (!config) throw new Error("未找到 OpenFic 实例配置");
    const instance = config.instances.find((item) => item.id === instanceId);
    if (!instance) throw new Error("实例不存在");
    startupProgress.update({
      step: "load-config",
      title: "读取实例配置",
      message: `正在切换到 ${instance.name}`,
      progress: 0.1,
    });
    const compatibilityWarning = await activateInstance(config, instance, startupProgress);
    await writeDesktopConfig({ ...config, activeInstanceId: instance.id });
    startupProgress.begin({
      step: "ready",
      title: "服务已就绪",
      message: "OpenFic 已准备完成",
      progress: 1,
    });
    startupProgress.complete();
    return { status: "ready", activeInstanceId: instance.id, compatibilityWarning: compatibilityWarning ?? undefined };
  } catch (error) {
    startupProgress.fail(error);
    throw error;
  }
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
  const startupProgress = createStartupProgress();
  startupProgress.begin({
    step: "load-config",
    title: "读取本地配置",
    message: "正在查找已有 OpenFic 实例",
    progress: 0.05,
  });
  try {
    const config = await readDesktopConfig();
    writeStartupLog(`config loaded: ${config ? `${config.instances.length} instances` : "none"}`);
    if (!config || config.instances.length === 0) {
      startupProgress.complete("尚未配置 OpenFic 实例");
      return { status: "needs-setup" };
    }
    const instance = getActiveInstance(config);
    if (!instance) {
      startupProgress.complete("尚未找到活动实例");
      return { status: "needs-setup" };
    }
    const compatibilityWarning = await activateInstance(config, instance, startupProgress);
    if (config.activeInstanceId !== instance.id) {
      await writeDesktopConfig({ ...config, activeInstanceId: instance.id });
    }
    startupProgress.begin({
      step: "ready",
      title: "服务已就绪",
      message: "OpenFic 已准备完成",
      progress: 1,
    });
    startupProgress.complete();
    return { status: "ready", activeInstanceId: instance.id, compatibilityWarning: compatibilityWarning ?? undefined };
  } catch (err) {
    writeStartupLog(`backend failed: ${err instanceof Error ? err.message : String(err)}`);
    startupProgress.fail(err);
    return {
      status: "needs-setup",
      activeInstanceId: null,
      message: err instanceof Error ? err.message : String(err),
    };
  }
}

async function bootstrap(): Promise<void> {
  writeStartupLog("bootstrap start");
  await configureDefaultSystemProxy();
  writeStartupLog("system proxy configured");
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
  if (mainWindow) await initializeUpdater(mainWindow);
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
