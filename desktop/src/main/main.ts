import { app, dialog, Menu, type BrowserWindow } from "electron";
import { mkdir } from "node:fs/promises";
import { registerAppScheme, handleAppProtocol, setRuntimeConfig } from "./protocol.js";
import { getDevDataDir, isDevMode, DEV_INSTANCE_ID, startDevBackend } from "./runtime/dev-backend.js";
import { createMainWindow } from "./windows.js";
import { readDesktopConfig, writeDesktopConfig } from "./config.js";
import { registerIpc } from "./ipc.js";
import { throwIfAborted, waitForBackend } from "./health.js";
import { ensurePortablePython, resolveRuntimeDir } from "./runtime/python.js";
import { ensureOpenFicRuntime, startLocalOpenFicBackend } from "./runtime/openfic.js";
import { forceStopBackendProcess, stopBackendProcess, type BackendProcessHandle } from "./process.js";
import { resolveDataDir } from "./data-location.js";
import { initializeUpdater } from "./updater.js";
import { configureDefaultSystemProxy } from "./proxy.js";
import { createStartupProgressTracker, type StartupProgressTracker } from "./startup-progress.js";
import { IpcChannels } from "../shared/ipc.js";
import { appendLog, setLogsDir } from "./logging.js";
import { captureException, captureExceptionImmediate, startErrorTelemetry, syncTelemetryEnabled } from "./telemetry.js";
import type { InitializeAppResult } from "../shared/ipc.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

function writeStartupLog(message: string): void {
  appendLog("startup", message);
}

let mainWindow: BrowserWindow | null = null;
let backendHandle: BackendProcessHandle | null = null;
let activeInstanceId: string | null = null;
let isQuitting = false;
let startupAbortController: AbortController | null = null;

writeStartupLog("process start");
startErrorTelemetry();
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
  if (previousHandle && previousHandle !== handle) void stopBackendProcess(previousHandle);
}

function clearBackend(): void {
  const previousHandle = backendHandle;
  backendHandle = null;
  if (previousHandle) void stopBackendProcess(previousHandle);
}

function isBackendRunning(): boolean {
  return backendHandle !== null;
}

async function stopActiveBackend(): Promise<void> {
  const handle = backendHandle;
  backendHandle = null;
  if (handle) await stopBackendProcess(handle);
}

function setBackendBaseUrl(url: string): void {
  const normalized = url.replace(/\/+$/, "");
  setRuntimeConfig({ backendBaseUrl: normalized });
  void syncTelemetryEnabled(normalized);
}

function onConfigSaved(config: DesktopConfig): void {
  activeInstanceId = isDevMode() ? DEV_INSTANCE_ID : config.activeInstanceId;
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

function beginStartupOperation(): AbortController {
  startupAbortController?.abort();
  const controller = new AbortController();
  startupAbortController = controller;
  return controller;
}

function finishStartupOperation(controller: AbortController): void {
  if (startupAbortController === controller) startupAbortController = null;
}

function cancelStartup(): void {
  startupAbortController?.abort();
}

async function startLocalBackend(
  installDir: string | null,
  dataDir: string,
  startupProgress: StartupProgressTracker,
  signal: AbortSignal,
): Promise<string | null> {
  throwIfAborted(signal);
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
  throwIfAborted(signal);
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
  throwIfAborted(signal);
  if (!runtimeWasUpdated) {
    startupProgress.update({
      step: "check-runtime",
      title: "检查运行环境",
      message: "运行环境已就绪",
      progress: 0.5,
    });
  }

  const { handle: backend, maintenanceError } = await startLocalOpenFicBackend(
    runtime.venvPythonPath,
    app.getVersion(),
    startupProgress,
    signal,
    dataDir,
  );
  setBackend(backend);
  setBackendBaseUrl(backend.baseUrl);
  return maintenanceError;
}

function getActiveInstance(config: DesktopConfig): DesktopInstance | null {
  return config.instances.find((instance) => instance.id === config.activeInstanceId) ?? config.instances[0] ?? null;
}

async function activateInstance(
  config: DesktopConfig,
  instance: DesktopInstance,
  startupProgress: StartupProgressTracker,
  signal: AbortSignal,
): Promise<{ compatibilityWarning: string | null; maintenanceWarning: string | null }> {
  throwIfAborted(signal);
  activeInstanceId = instance.id;
  setLogsDir(instance.mode === "local" ? resolveDataDir(instance) : null);
  if (instance.mode === "remote") {
    if (!instance.remoteUrl) throw new Error("远程实例缺少后端地址");
    startupProgress.begin({
      step: "connect-remote",
      title: "连接 OpenFic 服务",
      message: `正在连接 ${instance.remoteUrl}`,
      progress: 0.3,
    });
    const health = await waitForBackend(instance.remoteUrl, { timeoutMs: 10_000, signal });
    throwIfAborted(signal);
    startupProgress.begin({
      step: "verify-remote",
      title: "验证服务状态",
      message: "远程服务已响应，正在验证版本",
      progress: 0.7,
    });
    clearBackend();
    throwIfAborted(signal);
    setBackendBaseUrl(instance.remoteUrl);
    startupProgress.begin({
      step: "check-compatibility",
      title: "检查版本兼容性",
      message: "正在比较桌面端与后端版本",
      progress: 0.85,
    });
    if (health.version === app.getVersion()) return { compatibilityWarning: null, maintenanceWarning: null };
    return {
      compatibilityWarning: `远程实例版本为 ${health.version ?? "未知"}，桌面端版本为 ${app.getVersion()}，部分功能可能不兼容。`,
      maintenanceWarning: null,
    };
  }

  try {
    const maintenanceWarning = await startLocalBackend(instance.installDir, resolveDataDir(instance), startupProgress, signal);
    return { compatibilityWarning: null, maintenanceWarning };
  } catch (error) {
    appendLog("runtime", `本地运行环境更新或启动失败：${error instanceof Error ? error.message : String(error)}`);
    throw error;
  }
}

async function switchInstance(instanceId: string): Promise<InitializeAppResult> {
  if (isDevMode()) {
    if (instanceId !== DEV_INSTANCE_ID) throw new Error("开发模式下仅支持源码后端实例");
    const controller = beginStartupOperation();
    const startupProgress = createStartupProgress();
    startupProgress.begin({
      step: "load-config",
      title: "开发模式",
      message: "正在重启本地开发后端",
      progress: 0.1,
    });
    try {
      await stopActiveBackend();
      const devDataDir = getDevDataDir();
      await mkdir(devDataDir, { recursive: true });
      setLogsDir(devDataDir);
      const { handle, baseUrl, maintenanceError } = await startDevBackend(startupProgress, controller.signal);
      throwIfAborted(controller.signal);
      setBackendBaseUrl(baseUrl);
      if (handle) setBackend(handle);
      activeInstanceId = DEV_INSTANCE_ID;
      startupProgress.begin({
        step: "ready",
        title: "开发模式",
        message: "OpenFic 开发后端已就绪",
        progress: 1,
      });
      startupProgress.complete();
      return {
        status: "ready",
        activeInstanceId: DEV_INSTANCE_ID,
        maintenanceWarning: maintenanceError ?? undefined,
      };
    } catch (error) {
      if (controller.signal.aborted) startupProgress.complete("已取消连接");
      else startupProgress.fail(error);
      throw error;
    } finally {
      finishStartupOperation(controller);
    }
  }
  const controller = beginStartupOperation();
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
    const { compatibilityWarning, maintenanceWarning } = await activateInstance(config, instance, startupProgress, controller.signal);
    throwIfAborted(controller.signal);
    await writeDesktopConfig({ ...config, activeInstanceId: instance.id });
    throwIfAborted(controller.signal);
    startupProgress.begin({
      step: "ready",
      title: "服务已就绪",
      message: "OpenFic 已准备完成",
      progress: 1,
    });
    startupProgress.complete();
    return {
      status: "ready",
      activeInstanceId: instance.id,
      compatibilityWarning: compatibilityWarning ?? undefined,
      maintenanceWarning: maintenanceWarning ?? undefined,
    };
  } catch (error) {
    if (controller.signal.aborted) startupProgress.complete("已取消连接");
    else startupProgress.fail(error);
    throw error;
  } finally {
    finishStartupOperation(controller);
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

async function initializeDevApp(): Promise<InitializeAppResult> {
  const controller = beginStartupOperation();
  const startupProgress = createStartupProgress();
  startupProgress.begin({
    step: "load-config",
    title: "开发模式",
    message: "正在启动本地开发后端",
    progress: 0.1,
  });
  try {
    const devDataDir = getDevDataDir();
    await mkdir(devDataDir, { recursive: true });
    setLogsDir(devDataDir);
    activeInstanceId = DEV_INSTANCE_ID;
    const { handle, baseUrl, maintenanceError } = await startDevBackend(startupProgress, controller.signal);
    throwIfAborted(controller.signal);
    setBackendBaseUrl(baseUrl);
    if (handle) setBackend(handle);
    startupProgress.begin({
      step: "ready",
      title: "开发模式",
      message: "OpenFic 开发后端已就绪",
      progress: 1,
    });
    startupProgress.complete();
    return {
      status: "ready",
      activeInstanceId: DEV_INSTANCE_ID,
      maintenanceWarning: maintenanceError ?? undefined,
    };
  } catch (err) {
    if (controller.signal.aborted) {
      startupProgress.complete("已取消连接");
      return { status: "needs-setup" };
    }
    writeStartupLog(`dev backend failed: ${err instanceof Error ? err.message : String(err)}`);
    startupProgress.fail(err);
    return {
      status: "needs-setup",
      activeInstanceId: null,
      message: err instanceof Error ? err.message : String(err),
    };
  } finally {
    finishStartupOperation(controller);
  }
}

async function initializeApp(): Promise<InitializeAppResult> {
  if (isDevMode()) return initializeDevApp();
  const controller = beginStartupOperation();
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
    const { compatibilityWarning, maintenanceWarning } = await activateInstance(config, instance, startupProgress, controller.signal);
    throwIfAborted(controller.signal);
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
    return {
      status: "ready",
      activeInstanceId: instance.id,
      compatibilityWarning: compatibilityWarning ?? undefined,
      maintenanceWarning: maintenanceWarning ?? undefined,
    };
  } catch (err) {
    if (controller.signal.aborted) {
      startupProgress.complete("已取消连接");
      return { status: "needs-setup" };
    }
    writeStartupLog(`backend failed: ${err instanceof Error ? err.message : String(err)}`);
    startupProgress.fail(err);
    return {
      status: "needs-setup",
      activeInstanceId: null,
      message: err instanceof Error ? err.message : String(err),
    };
  } finally {
    finishStartupOperation(controller);
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
    setLogsDir,
    beginStartupOperation,
    finishStartupOperation,
    initializeApp,
    cancelStartup,
    switchInstance,
    pingInstance,
    onConfigSaved,
    isBackendRunning,
    stopActiveBackend,
  });

  writeStartupLog("opening shell window");
  openMainWindow();
  if (!isDevMode() && mainWindow) await initializeUpdater(mainWindow);
}

// Keep Chromium session data in Electron's default AppData location. Webviews
// remain isolated per instance through their persist:openfic-<id> partitions.
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

  app.on("before-quit", (event) => {
    if (isQuitting) return;
    const handle = backendHandle;
    if (!handle) {
      isQuitting = true;
      return;
    }

    event.preventDefault();
    isQuitting = true;
    void stopBackendProcess(handle).finally(() => app.quit());
  });

  process.on("exit", () => forceStopBackendProcess(backendHandle));
  process.on("SIGINT", () => {
    forceStopBackendProcess(backendHandle);
    process.exit(0);
  });
  process.on("SIGTERM", () => {
    forceStopBackendProcess(backendHandle);
    process.exit(0);
  });

  process.on("uncaughtException", (error) => {
    writeStartupLog(`uncaughtException: ${error.stack ?? error.message}`);
    void captureExceptionImmediate(error);
    throw error;
  });

  process.on("unhandledRejection", (reason) => {
    writeStartupLog(`unhandledRejection: ${reason instanceof Error ? reason.stack ?? reason.message : String(reason)}`);
    captureException(reason);
  });
}
