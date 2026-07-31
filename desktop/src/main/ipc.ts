import { app, dialog, ipcMain, shell, type BrowserWindow } from "electron";
import path from "node:path";
import {
  IpcChannels,
  type EnsureInstanceSessionRequest,
  type InitializeAppResult,
  type InspectLocalRuntimeRequest,
  type InspectLocalRuntimeResult,
  type InstallRuntimeRequest,
  type PingInstanceRequest,
  type PingInstanceResult,
  type SaveConfigRequest,
  type SaveZoomFactorRequest,
  type StartLocalBackendRequest,
  type SwitchInstanceRequest,
} from "../shared/ipc.js";
import { createDefaultConfig, readDesktopConfig, writeDesktopConfig } from "./config.js";
import { ensureAppProtocolForPartition } from "./protocol.js";
import { findLocalInstanceByInstallDir, normalizeInstallDir } from "./local-instance.js";
import { inspectLocalRuntime, installLocalRuntime, startLocalBackendFromInstall } from "./runtime/setup-runner.js";
import { getDefaultInstallDir } from "./runtime/python.js";
import { cancelUpdateDownload, checkForUpdates, downloadUpdate, getUpdateState, installUpdate, openUpdateRelease } from "./updater.js";
import { createStartupProgressTracker, getStartupProgress } from "./startup-progress.js";
import { exportLogs } from "./logging.js";
import type { BackendProcessHandle } from "./process.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

const PROJECT_HOME_URL = "https://github.com/syrizelink/OpenFic";
const BUG_REPORT_URL = `${PROJECT_HOME_URL}/issues/new?template=bug-report.yml`;
const FEATURE_SUGGESTION_URL = `${PROJECT_HOME_URL}/issues/new?template=feature-request.yml`;
const MIN_ZOOM_FACTOR = 0.7;
const MAX_ZOOM_FACTOR = 2.0;
const DEFAULT_ZOOM_FACTOR = 1.1;

function normalizeZoomFactor(zoomFactor: number): number {
  const clampedZoomFactor = Math.min(MAX_ZOOM_FACTOR, Math.max(MIN_ZOOM_FACTOR, zoomFactor));
  return Math.round(clampedZoomFactor * 10) / 10;
}

export interface IpcContext {
  shellWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  beginStartupOperation: () => AbortController;
  finishStartupOperation: (controller: AbortController) => void;
  initializeApp: () => Promise<InitializeAppResult>;
  cancelStartup: () => void;
  switchInstance: (instanceId: string) => Promise<InitializeAppResult>;
  pingInstance: (instance: DesktopInstance) => Promise<number>;
  onConfigSaved: (config: DesktopConfig) => void;
}

function createInstanceId(): string {
  return `instance-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function registerIpc(context: IpcContext): void {
  let pendingZoomSave = Promise.resolve();

  const saveZoomFactor = async (zoomFactor: number): Promise<number> => {
    const clampedZoomFactor = normalizeZoomFactor(zoomFactor);
    const save = pendingZoomSave.then(async () => {
      const config = await readDesktopConfig();
      await writeDesktopConfig({ ...(config ?? createDefaultConfig()), zoomFactor: clampedZoomFactor });
    });
    pendingZoomSave = save.catch(() => undefined);
    await save;
    context.shellWindow()?.webContents.send(IpcChannels.zoomFactorChanged, clampedZoomFactor);
    return clampedZoomFactor;
  };

  ipcMain.handle(IpcChannels.getConfig, () => readDesktopConfig());

  ipcMain.handle(IpcChannels.saveConfig, async (_event, request: SaveConfigRequest) => {
    await pendingZoomSave;
    const previousConfig = await readDesktopConfig();
    const nextConfig = { ...request.config, zoomFactor: previousConfig?.zoomFactor };
    await writeDesktopConfig(nextConfig);
    context.onConfigSaved(nextConfig);
  });

  ipcMain.handle(IpcChannels.getZoomFactor, async () => {
    await pendingZoomSave;
    return normalizeZoomFactor((await readDesktopConfig())?.zoomFactor ?? DEFAULT_ZOOM_FACTOR);
  });

  ipcMain.handle(IpcChannels.saveZoomFactor, async (_event, request: SaveZoomFactorRequest) => {
    if (!Number.isFinite(request.zoomFactor)) return;
    return saveZoomFactor(request.zoomFactor);
  });

  ipcMain.handle(IpcChannels.initializeApp, () => context.initializeApp());
  ipcMain.handle(IpcChannels.cancelStartup, () => context.cancelStartup());
  ipcMain.handle(IpcChannels.getStartupProgress, () => getStartupProgress());
  ipcMain.handle(IpcChannels.getUpdateState, () => getUpdateState());
  ipcMain.handle(IpcChannels.checkForUpdate, () => checkForUpdates());
  ipcMain.handle(IpcChannels.downloadUpdate, () => downloadUpdate());
  ipcMain.handle(IpcChannels.cancelUpdateDownload, () => cancelUpdateDownload());
  ipcMain.handle(IpcChannels.installUpdate, () => installUpdate());
  ipcMain.handle(IpcChannels.openUpdateRelease, () => openUpdateRelease());
  ipcMain.handle(IpcChannels.exportLogs, async () => {
    const defaultPath = path.join(
      app.getPath("downloads"),
      `openfic-backend-logs-${new Date().toISOString().replace(/[:.]/g, "-")}.zip`,
    );
    const window = context.shellWindow();
    const result = window
      ? await dialog.showSaveDialog(window, {
          defaultPath,
          filters: [{ name: "ZIP 压缩包", extensions: ["zip"] }],
          title: "导出后端日志",
        })
      : await dialog.showSaveDialog({
          defaultPath,
          filters: [{ name: "ZIP 压缩包", extensions: ["zip"] }],
          title: "导出后端日志",
        });
    if (result.canceled || !result.filePath) return null;

    try {
      return await exportLogs(result.filePath);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      dialog.showErrorBox("导出后端日志失败", message);
      throw error;
    }
  });

  ipcMain.handle(IpcChannels.ensureInstanceSession, (_event, request: EnsureInstanceSessionRequest) => {
    return ensureAppProtocolForPartition(request.partition);
  });

  ipcMain.handle(IpcChannels.getDefaultInstallDir, () => getDefaultInstallDir());

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

  ipcMain.handle(
    IpcChannels.inspectLocalRuntime,
    async (_event, request: InspectLocalRuntimeRequest): Promise<InspectLocalRuntimeResult> => {
      const [runtime, config] = await Promise.all([inspectLocalRuntime(request.installDir), readDesktopConfig()]);
      return {
        ...runtime,
        configuredInstance: findLocalInstanceByInstallDir(config, request.installDir),
      };
    },
  );

  ipcMain.handle(IpcChannels.installRuntime, async (_event, request: InstallRuntimeRequest) => {
    const window = context.shellWindow();
    if (!window) throw new Error("shell window is not available");
    await installLocalRuntime(window.webContents, request.installDir);
  });

  ipcMain.handle(IpcChannels.startLocalBackend, async (_event, request: StartLocalBackendRequest) => {
    const window = context.shellWindow();
    if (!window) throw new Error("shell window is not available");
    const controller = context.beginStartupOperation();
    const startupProgress = createStartupProgressTracker((progress) => {
      window.webContents.send(IpcChannels.startupProgress, progress);
    });
    try {
      const backend = await startLocalBackendFromInstall(request.installDir, startupProgress, controller.signal);
      context.setBackend(backend);
      context.setBackendBaseUrl(backend.baseUrl);
      await pendingZoomSave;
      const previousConfig = await readDesktopConfig();
      const existingInstance = findLocalInstanceByInstallDir(previousConfig, request.installDir);
      const instance: DesktopInstance = existingInstance ?? {
        id: createInstanceId(),
        name: "Local",
        mode: "local",
        remoteUrl: null,
        autoStartLocal: true,
        installDir: request.installDir,
      };
      const normalizedInstallDir = normalizeInstallDir(request.installDir);
      const nextConfig: DesktopConfig = {
        activeInstanceId: instance.id,
        instances: [
          ...(previousConfig?.instances ?? []).filter(
            (candidate) =>
              candidate.mode !== "local" ||
              candidate.installDir === null ||
              normalizeInstallDir(candidate.installDir) !== normalizedInstallDir,
          ),
          instance,
        ],
        zoomFactor: previousConfig?.zoomFactor,
      };
      await writeDesktopConfig(nextConfig);
      context.onConfigSaved(nextConfig);
      startupProgress.begin({
        step: "ready",
        title: "服务已就绪",
        message: "OpenFic 已准备完成",
        progress: 1,
      });
      startupProgress.complete();
    } catch (error) {
      if (controller.signal.aborted) startupProgress.complete("已取消连接");
      else startupProgress.fail(error);
      throw error;
    } finally {
      context.finishStartupOperation(controller);
    }
  });

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
  ipcMain.handle(IpcChannels.toggleFullScreen, async () => {
    const window = context.shellWindow();
    if (!window) return;
    window.setFullScreen(!window.isFullScreen());
  });
  ipcMain.handle(IpcChannels.reloadWindow, () => {
    context.shellWindow()?.webContents.reload();
  });
  ipcMain.handle(IpcChannels.toggleDevTools, () => {
    const webContents = context.shellWindow()?.webContents;
    if (!webContents) return;
    if (webContents.isDevToolsOpened()) {
      webContents.closeDevTools();
      return;
    }
    webContents.openDevTools({ mode: "detach", title: "OpenFic 开发者工具" });
  });
  ipcMain.handle(IpcChannels.closeWindow, async () => {
    context.shellWindow()?.close();
  });
  ipcMain.handle(IpcChannels.openProjectHome, () => shell.openExternal(PROJECT_HOME_URL));
  ipcMain.handle(IpcChannels.reportBug, () => shell.openExternal(BUG_REPORT_URL));
  ipcMain.handle(IpcChannels.suggestFeature, () => shell.openExternal(FEATURE_SUGGESTION_URL));
}
