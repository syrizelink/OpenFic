import type { BrowserWindow } from "electron";
import { IpcChannels, type CheckRemoteRequest, type InitializeAppResult, type SaveConfigRequest } from "../shared/ipc.js";
import { readDesktopConfig, writeDesktopConfig } from "./config.js";
import { waitForBackend } from "./health.js";
import { runLocalSetup } from "./runtime/setup-runner.js";
import type { BackendProcessHandle } from "./process.js";

const electron = require("electron") as typeof import("electron");

const { ipcMain } = electron;

export interface IpcContext {
  shellWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  initializeApp: () => Promise<InitializeAppResult>;
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

  ipcMain.handle(IpcChannels.checkRemote, async (_event, request: CheckRemoteRequest) => {
    await waitForBackend(request.url, 10_000);
  });

  ipcMain.handle(IpcChannels.runLocalSetup, async () => {
    const window = context.shellWindow();
    if (!window) throw new Error("shell window is not available");
    const backend = await runLocalSetup(window.webContents);
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
