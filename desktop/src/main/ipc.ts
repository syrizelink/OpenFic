import type { BrowserWindow } from "electron";
import { readdir, stat } from "node:fs/promises";
import {
  IpcChannels,
  type CheckDirectoryEmptyRequest,
  type CheckDirectoryEmptyResult,
  type CheckRemoteRequest,
  type InitializeAppResult,
  type InstallRuntimeRequest,
  type SaveConfigRequest,
  type StartLocalBackendRequest,
} from "../shared/ipc.js";
import { readDesktopConfig, writeDesktopConfig } from "./config.js";
import { waitForBackend } from "./health.js";
import { installLocalRuntime, startLocalBackendFromInstall } from "./runtime/setup-runner.js";
import { getDefaultInstallDir } from "./runtime/python.js";
import type { BackendProcessHandle } from "./process.js";

const electron = require("electron") as typeof import("electron");

const { ipcMain, dialog } = electron;

export interface IpcContext {
  shellWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  initializeApp: () => Promise<InitializeAppResult>;
}

async function isDirectoryEmpty(dirPath: string): Promise<CheckDirectoryEmptyResult> {
  try {
    const info = await stat(dirPath);
    if (!info.isDirectory()) return { exists: false, empty: false };
  } catch {
    return { exists: false, empty: false };
  }
  try {
    const entries = await readdir(dirPath);
    return { exists: true, empty: entries.length === 0 };
  } catch {
    return { exists: true, empty: false };
  }
}

export function registerIpc(context: IpcContext): void {
  ipcMain.handle(IpcChannels.getConfig, () => readDesktopConfig());

  ipcMain.handle(IpcChannels.saveConfig, async (_event, request: SaveConfigRequest) => {
    await writeDesktopConfig(request.config);
    if (request.config.mode === "remote" && request.config.remoteUrl) {
      context.setBackendBaseUrl(request.config.remoteUrl);
    }
  });

  ipcMain.handle(IpcChannels.initializeApp, () => context.initializeApp());

  ipcMain.handle(IpcChannels.getDefaultInstallDir, () => getDefaultInstallDir());

  ipcMain.handle(IpcChannels.checkRemote, async (_event, request: CheckRemoteRequest) => {
    await waitForBackend(request.url, 10_000);
  });

  ipcMain.handle(IpcChannels.selectDirectory, async () => {
    const window = context.shellWindow();
    const options: Electron.OpenDialogOptions = {
      properties: ["openDirectory", "createDirectory"],
    };
    const result = window
      ? await dialog.showOpenDialog(window, options)
      : await dialog.showOpenDialog(options);
    if (result.canceled || !result.filePaths.length) return null;
    return result.filePaths[0];
  });

  ipcMain.handle(IpcChannels.checkDirectoryEmpty, async (_event, request: CheckDirectoryEmptyRequest) =>
    isDirectoryEmpty(request.path),
  );

  ipcMain.handle(IpcChannels.installRuntime, async (_event, request: InstallRuntimeRequest) => {
    const window = context.shellWindow();
    if (!window) throw new Error("shell window is not available");
    await installLocalRuntime(window.webContents, request.installDir);
  });

  ipcMain.handle(IpcChannels.startLocalBackend, async (_event, request: StartLocalBackendRequest) => {
    const backend = await startLocalBackendFromInstall(request.installDir);
    context.setBackend(backend);
    context.setBackendBaseUrl(backend.baseUrl);
  });

  ipcMain.handle(IpcChannels.closeSetup, async () => undefined);
  ipcMain.handle(IpcChannels.showSetup, async () => undefined);
  ipcMain.handle(IpcChannels.minimizeWindow, async () => {
    context.shellWindow()?.minimize();
  });
  ipcMain.handle(IpcChannels.toggleMaximizeWindow, async () => {
    const window = context.shellWindow();
    if (!window) return;
    if (window.isMaximized()) {
      window.unmaximize();
      return;
    }
    window.maximize();
  });
  ipcMain.handle(IpcChannels.closeWindow, async () => {
    context.shellWindow()?.close();
  });
}
