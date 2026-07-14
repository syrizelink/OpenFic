import { app, shell, type BrowserWindow } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";
import electronUpdater, { CancellationToken, NsisUpdater, type ProgressInfo, type UpdateInfo } from "electron-updater";
import { IpcChannels, type UpdateState } from "../shared/ipc.js";
import { isAutoUpdateSupported } from "./update-support.js";
import { configureSystemProxy } from "./proxy.js";

const { autoUpdater } = electronUpdater;

let shellWindow: BrowserWindow | null = null;
let updateState: UpdateState = { status: "idle" };
let initialized = false;
let downloadCancellationToken: CancellationToken | null = null;

function publishState(nextState: UpdateState): void {
  updateState = nextState;
  shellWindow?.webContents.send(IpcChannels.updateState, nextState);
}

function describeError(error: Error): string {
  return error.message || "更新服务暂时不可用";
}

function getReleaseNotes(info: UpdateInfo): string | undefined {
  if (typeof info.releaseNotes === "string") return info.releaseNotes.trim() || undefined;
  if (!Array.isArray(info.releaseNotes)) return undefined;
  const notes = info.releaseNotes
    .map((item) => item.note?.trim())
    .filter((item): item is string => Boolean(item));
  return notes.length ? notes.join("\n\n") : undefined;
}

function onUpdateAvailable(info: UpdateInfo): void {
  publishState({ status: "available", version: info.version, releaseNotes: getReleaseNotes(info) });
}

function onDownloadProgress(progress: ProgressInfo): void {
  publishState({
    ...updateState,
    status: "downloading",
    progress: progress.percent / 100,
    transferred: progress.transferred,
    total: progress.total,
    bytesPerSecond: progress.bytesPerSecond,
  });
}

function onUpdateCancelled(info: UpdateInfo): void {
  publishState({ status: "available", version: info.version, releaseNotes: getReleaseNotes(info) });
}

function canUseAutoUpdater(): boolean {
  if (!app.isPackaged) return false;
  return isAutoUpdateSupported({
    platform: process.platform,
    arch: process.arch,
  });
}

function configurePortableInstallDirectory(): void {
  const installDirectory = path.dirname(app.getPath("exe"));
  const uninstallerPath = path.join(installDirectory, "Uninstall OpenFic.exe");
  if (!existsSync(uninstallerPath) && autoUpdater instanceof NsisUpdater) {
    autoUpdater.installDirectory = installDirectory;
  }
}

export async function initializeUpdater(window: BrowserWindow): Promise<void> {
  shellWindow = window;
  await configureSystemProxy(autoUpdater.netSession);
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
  configurePortableInstallDirectory();
  autoUpdater.on("checking-for-update", () => publishState({ status: "checking" }));
  autoUpdater.on("update-available", onUpdateAvailable);
  autoUpdater.on("update-not-available", () => publishState({ status: "not-available" }));
  autoUpdater.on("download-progress", onDownloadProgress);
  autoUpdater.on("update-cancelled", onUpdateCancelled);
  autoUpdater.on("update-downloaded", (info) => publishState({ status: "downloaded", version: info.version, releaseNotes: getReleaseNotes(info) }));
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

  publishState({ status: "checking" });
  try {
    await autoUpdater.checkForUpdates();
  } catch (error) {
    publishState({ status: "error", message: describeError(error instanceof Error ? error : new Error(String(error))) });
  }
}

export async function downloadUpdate(): Promise<void> {
  if (updateState.status !== "available") return;

  publishState({
    status: "downloading",
    version: updateState.version,
    releaseNotes: updateState.releaseNotes,
    progress: 0,
    transferred: 0,
  });
  const cancellationToken = new CancellationToken();
  downloadCancellationToken = cancellationToken;
  try {
    await autoUpdater.downloadUpdate(cancellationToken);
  } catch (error) {
    if (!cancellationToken.cancelled) {
      publishState({ status: "error", message: describeError(error instanceof Error ? error : new Error(String(error))) });
    }
  } finally {
    if (downloadCancellationToken === cancellationToken) downloadCancellationToken = null;
  }
}

export function cancelUpdateDownload(): void {
  if (updateState.status !== "downloading") return;
  downloadCancellationToken?.cancel();
}

export function installUpdate(): void {
  if (updateState.status !== "downloaded") return;
  autoUpdater.quitAndInstall(true, true);
}

export async function openUpdateRelease(): Promise<void> {
  if (!updateState.version) return;
  await shell.openExternal(`https://github.com/syrizelink/OpenFic/releases/tag/v${encodeURIComponent(updateState.version)}`);
}
