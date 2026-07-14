import type { BrowserWindow } from "electron";
import { readdir, stat } from "node:fs/promises";
import {
  IpcChannels,
  type CheckDirectoryEmptyRequest,
  type CheckDirectoryEmptyResult,
  type CheckRemoteRequest,
  type EnsureInstanceSessionRequest,
  type InitializeAppResult,
  type InstallRuntimeRequest,
  type PingInstanceRequest,
  type PingInstanceResult,
  type SaveConfigRequest,
  type StartLocalBackendRequest,
  type SwitchInstanceRequest,
} from "../shared/ipc.js";
import { readDesktopConfig, writeDesktopConfig } from "./config.js";
import { waitForBackend } from "./health.js";
import { ensureAppProtocolForPartition } from "./protocol.js";
import { installLocalRuntime, startLocalBackendFromInstall } from "./runtime/setup-runner.js";
import { getDefaultInstallDir } from "./runtime/python.js";
import type { BackendProcessHandle } from "./process.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";
import { checkForUpdates, downloadUpdate, getUpdateState, installUpdate } from "./updater.js";

const electron = require("electron") as typeof import("electron");

const { ipcMain, dialog } = electron;

export interface IpcContext {
  shellWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  initializeApp: () => Promise<InitializeAppResult>;
  switchInstance: (instanceId: string) => Promise<InitializeAppResult>;
  pingInstance: (instance: DesktopInstance) => Promise<number>;
  onConfigSaved: (config: DesktopConfig) => void;
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
    context.onConfigSaved(request.config);
  });

  ipcMain.handle(IpcChannels.initializeApp, () => context.initializeApp());
  ipcMain.handle(IpcChannels.getUpdateState, () => getUpdateState());
  ipcMain.handle(IpcChannels.checkForUpdate, () => checkForUpdates());
  ipcMain.handle(IpcChannels.downloadUpdate, () => downloadUpdate());
  ipcMain.handle(IpcChannels.installUpdate, () => installUpdate());

  ipcMain.handle(IpcChannels.ensureInstanceSession, (_event, request: EnsureInstanceSessionRequest) => {
    ensureAppProtocolForPartition(request.partition);
  });

  ipcMain.handle(IpcChannels.getDefaultInstallDir, () => getDefaultInstallDir());

  ipcMain.handle(IpcChannels.checkRemote, async (_event, request: CheckRemoteRequest) => {
    await waitForBackend(request.url, 10_000);
  });

  ipcMain.handle(IpcChannels.switchInstance, (_event, request: SwitchInstanceRequest) =>
    context.switchInstance(request.instanceId),
  );

  ipcMain.handle(IpcChannels.pingInstance, async (_event, request: PingInstanceRequest): Promise<PingInstanceResult> => {
    const latencyMs = await context.pingInstance(request.instance);
    return { latencyMs };
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
