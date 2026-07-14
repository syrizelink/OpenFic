import type { BrowserWindow } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";
import { autoUpdater } from "electron-updater";
import type { ProgressInfo, UpdateInfo } from "electron-updater";
import { IpcChannels, type UpdateState } from "../shared/ipc.js";
import { isAutoUpdateSupported } from "./update-support.js";

const electron = require("electron") as typeof import("electron");

const { app } = electron;

let shellWindow: BrowserWindow | null = null;
let updateState: UpdateState = { status: "idle" };
let initialized = false;

function publishState(nextState: UpdateState): void {
  updateState = nextState;
  shellWindow?.webContents.send(IpcChannels.updateState, nextState);
}

function describeError(error: Error): string {
  return error.message || "更新服务暂时不可用";
}

function onUpdateAvailable(info: UpdateInfo): void {
  publishState({ status: "available", version: info.version });
}

function onDownloadProgress(progress: ProgressInfo): void {
  publishState({
    status: "downloading",
    progress: progress.percent / 100,
    transferred: progress.transferred,
    total: progress.total,
  });
}

function canUseAutoUpdater(): boolean {
  if (!app.isPackaged || process.platform !== "win32" || process.arch !== "x64") return false;
  const uninstallerPath = path.join(path.dirname(app.getPath("exe")), "Uninstall OpenFic.exe");
  return isAutoUpdateSupported({
    platform: process.platform,
    arch: process.arch,
    hasNsisUninstaller: existsSync(uninstallerPath),
  });
}

export function initializeUpdater(window: BrowserWindow): void {
  shellWindow = window;
  if (initialized) {
    window.webContents.send(IpcChannels.updateState, updateState);
    return;
  }

  initialized = true;
  if (!canUseAutoUpdater()) {
    publishState({ status: "unsupported" });
    return;
  }

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = false;
  autoUpdater.on("checking-for-update", () => publishState({ status: "checking" }));
  autoUpdater.on("update-available", onUpdateAvailable);
  autoUpdater.on("update-not-available", () => publishState({ status: "not-available" }));
  autoUpdater.on("download-progress", onDownloadProgress);
  autoUpdater.on("update-downloaded", (info) => publishState({ status: "downloaded", version: info.version }));
  autoUpdater.on("error", (error) => publishState({ status: "error", message: describeError(error) }));
  publishState({ status: "idle" });
}

export function getUpdateState(): UpdateState {
  return updateState;
}

export async function checkForUpdates(): Promise<void> {
  if (!canUseAutoUpdater()) {
    publishState({ status: "unsupported" });
    return;
  }

  try {
    await autoUpdater.checkForUpdates();
  } catch (error) {
    publishState({ status: "error", message: describeError(error instanceof Error ? error : new Error(String(error))) });
  }
}

export async function downloadUpdate(): Promise<void> {
  if (updateState.status !== "available") return;

  try {
    await autoUpdater.downloadUpdate();
  } catch (error) {
    publishState({ status: "error", message: describeError(error instanceof Error ? error : new Error(String(error))) });
  }
}

export function installUpdate(): void {
  if (updateState.status !== "downloaded") return;
  autoUpdater.quitAndInstall(false, true);
}
