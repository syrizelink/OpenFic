import type { BrowserWindow } from "electron";
import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { registerAppScheme, handleAppProtocol, setRuntimeConfig } from "./protocol.js";
import { createMainWindow } from "./windows.js";
import { readDesktopConfig } from "./config.js";
import { registerIpc } from "./ipc.js";
import { waitForBackend } from "./health.js";
import { ensurePortablePython } from "./runtime/python.js";
import { ensureOpenFicRuntime, startLocalOpenFicBackend } from "./runtime/openfic.js";
import { stopBackendProcess, type BackendProcessHandle } from "./process.js";
import type { InitializeAppResult } from "../shared/ipc.js";

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
let isQuitting = false;

writeStartupLog("process start");
registerAppScheme();
writeStartupLog("scheme registered");

function setBackend(handle: BackendProcessHandle): void {
  backendHandle = handle;
  backendHandle.process.on("exit", () => {
    backendHandle = null;
    if (!isQuitting) {
      dialog.showErrorBox("OpenFic 后端已退出", `后端服务异常退出。日志路径：${handle.logPath}`);
      app.quit();
    }
  });
}

function setBackendBaseUrl(url: string): void {
  setRuntimeConfig({ backendBaseUrl: url.replace(/\/+$/, "") });
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

async function startLocalBackend(): Promise<void> {
  const python = await ensurePortablePython(() => undefined);
  const runtime = await ensureOpenFicRuntime(python, () => undefined);
  const backend = await startLocalOpenFicBackend(runtime.uvPath);
  setBackend(backend);
  setBackendBaseUrl(backend.baseUrl);
}

function installMenu(): void {
  Menu.setApplicationMenu(null);
}

async function initializeApp(): Promise<InitializeAppResult> {
  const config = await readDesktopConfig();
  writeStartupLog(`config loaded: ${config ? config.mode : "none"}`);

  if (!config) {
    return { status: "needs-setup" };
  }

  if (config.mode === "remote") {
    if (!config.remoteUrl) {
      return { status: "needs-setup" };
    }

    try {
      await waitForBackend(config.remoteUrl, 10_000);
      setBackendBaseUrl(config.remoteUrl);
      return { status: "ready" };
    } catch (err) {
      writeStartupLog(`remote backend failed: ${err instanceof Error ? err.message : String(err)}`);
      return {
        status: "needs-setup",
        message: err instanceof Error ? err.message : String(err),
      };
    }
  }

  try {
    await startLocalBackend();
    return { status: "ready" };
  } catch (err) {
    writeStartupLog(`local backend failed: ${err instanceof Error ? err.message : String(err)}`);
    return {
      status: "needs-setup",
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
