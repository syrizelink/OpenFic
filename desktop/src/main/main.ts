import { app, dialog, Menu } from "electron";
import type { BrowserWindow } from "electron";
import { registerAppScheme, handleAppProtocol, setRuntimeConfig } from "./protocol.js";
import { createMainWindow, createSetupWindow } from "./windows.js";
import { readDesktopConfig } from "./config.js";
import { registerIpc } from "./ipc.js";
import { waitForBackend } from "./health.js";
import { ensurePortablePython } from "./runtime/python.js";
import { ensureOpenFicRuntime, startLocalOpenFicBackend } from "./runtime/openfic.js";
import { stopBackendProcess, type BackendProcessHandle } from "./process.js";

let mainWindow: BrowserWindow | null = null;
let setupWindow: BrowserWindow | null = null;
let backendHandle: BackendProcessHandle | null = null;
let isQuitting = false;

registerAppScheme();

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

function openMainWindow(): void {
  if (mainWindow) {
    mainWindow.focus();
    return;
  }
  mainWindow = createMainWindow();
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function openSetupWindow(): void {
  if (setupWindow) {
    setupWindow.focus();
    return;
  }
  setupWindow = createSetupWindow();
  setupWindow.on("closed", () => {
    setupWindow = null;
  });
}

async function startLocalBackend(): Promise<void> {
  const python = await ensurePortablePython(() => undefined);
  const runtime = await ensureOpenFicRuntime(python, () => undefined);
  const backend = await startLocalOpenFicBackend(runtime.uvPath);
  setBackend(backend);
  setBackendBaseUrl(backend.baseUrl);
}

function installMenu(): void {
  const menu = Menu.buildFromTemplate([
    {
      label: "OpenFic",
      submenu: [
        { label: "设置", click: openSetupWindow },
        { type: "separator" },
        { role: "quit", label: "退出" },
      ],
    },
  ]);
  Menu.setApplicationMenu(menu);
}

async function bootstrap(): Promise<void> {
  handleAppProtocol();
  installMenu();
  registerIpc({
    setupWindow: () => setupWindow,
    setBackend,
    setBackendBaseUrl,
    openMainWindow,
  });

  const config = await readDesktopConfig();
  if (!config) {
    openSetupWindow();
    return;
  }

  if (config.mode === "remote") {
    if (!config.remoteUrl) {
      openSetupWindow();
      return;
    }
    try {
      await waitForBackend(config.remoteUrl, 10_000);
      setBackendBaseUrl(config.remoteUrl);
      openMainWindow();
    } catch (err) {
      dialog.showErrorBox("远程后端不可用", err instanceof Error ? err.message : String(err));
      openSetupWindow();
    }
    return;
  }

  try {
    await startLocalBackend();
    openMainWindow();
  } catch (err) {
    dialog.showErrorBox("本地后端启动失败", err instanceof Error ? err.message : String(err));
    openSetupWindow();
  }
}

const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
      return;
    }
    if (setupWindow) setupWindow.focus();
  });

  app.whenReady().then(() => {
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
}
