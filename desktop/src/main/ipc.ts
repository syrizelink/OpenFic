import { app, dialog, ipcMain, session, shell, webContents, type BrowserWindow } from "electron";
import path from "node:path";
import {
  IpcChannels,
  type BackupDataRequest,
  type DataProgressEvent,
  type EnsureInstanceSessionRequest,
  type GetDataInfoRequest,
  type InitializeAppResult,
  type InspectDataDirRequest,
  type InspectLocalRuntimeRequest,
  type InspectLocalRuntimeResult,
  type InstallRuntimeRequest,
  type LogFrontendDiagnosticRequest,
  type MigrateDataRequest,
  type MigrateDataResult,
  type PingInstanceRequest,
  type PingInstanceResult,
  type RestoreDataRequest,
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
import { getDefaultDataDir, resolveDataDir } from "./data-location.js";
import {
  backupDataDir,
  inspectDataDir,
  migrateDataDir,
  removeDataDir,
  restoreDataDir,
} from "./data-manager.js";
import { cancelUpdateDownload, checkForUpdates, downloadUpdate, getUpdateState, installUpdate, openUpdateRelease } from "./updater.js";
import { createStartupProgressTracker, getStartupProgress } from "./startup-progress.js";
import { appendLog, exportLogs } from "./logging.js";
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
  isBackendRunning: () => boolean;
  stopActiveBackend: () => Promise<void>;
}

function createInstanceId(): string {
  return `instance-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

const WEBVIEW_SHUTDOWN_WAIT_MS = 10_000;

async function waitForInstanceWebViews(instanceId: string): Promise<void> {
  const targetSession = session.fromPartition(`persist:openfic-${instanceId}`);
  const guests = webContents
    .getAllWebContents()
    .filter((contents) => contents.session === targetSession && !contents.isDestroyed());
  if (guests.length === 0) return;
  await Promise.race([
    Promise.all(
      guests.map(
        (contents) =>
          new Promise<void>((resolve) => {
            contents.once("destroyed", () => resolve());
          }),
      ),
    ),
    new Promise<void>((resolve) => setTimeout(resolve, WEBVIEW_SHUTDOWN_WAIT_MS)),
  ]);
}

export function registerIpc(context: IpcContext): void {
  let pendingZoomSave = Promise.resolve();

  async function withBackendRestart<T>(instanceId: string, operation: () => Promise<T>): Promise<T> {
    await waitForInstanceWebViews(instanceId);
    const wasRunning = context.isBackendRunning();
    if (wasRunning) await context.stopActiveBackend();
    return operation();
  }

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

  ipcMain.handle(IpcChannels.logFrontendDiagnostic, (_event, request: LogFrontendDiagnosticRequest) => {
    if (typeof request?.message !== "string") return;
    appendLog("connect", request.message.slice(0, 4_000));
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

  ipcMain.handle(IpcChannels.selectSaveFile, async () => {
    const window = context.shellWindow();
    const defaultPath = path.join(
      app.getPath("downloads"),
      `openfic-data-backup-${new Date().toISOString().replace(/[:.]/g, "-")}.tar.gz`,
    );
    const options: Electron.SaveDialogOptions = {
      defaultPath,
      filters: [{ name: "OpenFic 数据备份", extensions: ["tar.gz"] }],
      title: "备份作品数据",
    };
    const result = window
      ? await dialog.showSaveDialog(window, options)
      : await dialog.showSaveDialog(options);
    if (result.canceled || !result.filePath) return null;
    return result.filePath;
  });

  ipcMain.handle(IpcChannels.selectOpenFile, async () => {
    const window = context.shellWindow();
    const options: Electron.OpenDialogOptions = {
      properties: ["openFile"],
      filters: [{ name: "OpenFic 数据备份", extensions: ["tar.gz"] }],
      title: "选择数据备份文件",
    };
    const result = window
      ? await dialog.showOpenDialog(window, options)
      : await dialog.showOpenDialog(options);
    if (result.canceled || !result.filePaths.length) return null;
    return result.filePaths[0];
  });

  ipcMain.handle(IpcChannels.getDefaultDataDir, () => getDefaultDataDir());

  ipcMain.handle(IpcChannels.getDataInfo, async (_event, request: GetDataInfoRequest) => {
    const config = await readDesktopConfig();
    const instance = config?.instances.find((item) => item.id === request.instanceId);
    if (!instance) throw new Error("实例不存在");
    const dataDir = resolveDataDir(instance);
    const inspection = await inspectDataDir(dataDir);
    return {
      dataDir,
      isDefaultLocation: instance.dataDir === null,
      hasData: inspection.hasData,
      entryCount: inspection.entryCount,
      sizeBytes: inspection.sizeBytes,
    };
  });

  ipcMain.handle(IpcChannels.inspectDataDir, async (_event, request: InspectDataDirRequest) => {
    return inspectDataDir(request.dataDir);
  });

  ipcMain.handle(IpcChannels.migrateData, async (_event, request: MigrateDataRequest): Promise<MigrateDataResult> => {
    const config = await readDesktopConfig();
    if (!config) throw new Error("未找到 OpenFic 实例配置");
    const instance = config.instances.find((item) => item.id === request.instanceId);
    if (!instance) throw new Error("实例不存在");
    const sourceDir = resolveDataDir(instance);
    const targetDir = path.resolve(request.newDataDir);

    const result = await withBackendRestart(request.instanceId, async () => {
      let migrated = false;
      let removedOldDir = false;
      const emitProgress = (event: DataProgressEvent) =>
        context.shellWindow()?.webContents.send(IpcChannels.dataProgress, event);
      const targetInspection = await inspectDataDir(targetDir);
      const nextConfig: DesktopConfig = {
        ...config,
        instances: config.instances.map((item) =>
          item.id === instance.id ? { ...item, dataDir: targetDir } : item,
        ),
      };
      if (!targetInspection.hasData) {
        appendLog("data", `开始迁移数据目录：${sourceDir} -> ${targetDir}`);
        await migrateDataDir(sourceDir, targetDir, (message) => appendLog("data", message), (phase, progress) =>
          emitProgress({ operation: "migrate", phase, progress }),
        );
        migrated = true;
        appendLog("data", `数据迁移完成：${targetDir}`);

        if (request.deleteOldDir && normalizeInstallDir(sourceDir) !== normalizeInstallDir(targetDir)) {
          try {
            emitProgress({ operation: "migrate", phase: "delete-old" });
            await removeDataDir(sourceDir);
            removedOldDir = true;
            appendLog("data", `已删除原数据目录：${sourceDir}`);
          } catch (error) {
            appendLog("data", `删除原数据目录失败（迁移已成功）：${error instanceof Error ? error.message : String(error)}`);
          }
        }
      } else {
        appendLog("data", `切换数据目录（目标已含数据）：${sourceDir} -> ${targetDir}`);
      }
      await writeDesktopConfig(nextConfig);
      context.onConfigSaved(nextConfig);
      return { dataDir: targetDir, migrated, removedOldDir };
    });
    return result;
  });

  ipcMain.handle(IpcChannels.backupData, async (_event, request: BackupDataRequest): Promise<void> => {
    const config = await readDesktopConfig();
    const instance = config?.instances.find((item) => item.id === request.instanceId);
    if (!instance) throw new Error("实例不存在");
    await withBackendRestart(request.instanceId, async () => {
      const emitProgress = (event: DataProgressEvent) =>
        context.shellWindow()?.webContents.send(IpcChannels.dataProgress, event);
      appendLog("data", `开始备份数据目录：${resolveDataDir(instance)} -> ${request.targetPath}`);
      await backupDataDir(resolveDataDir(instance), request.targetPath, (message) => appendLog("data", message), (phase, progress) =>
        emitProgress({ operation: "backup", phase, progress }),
      );
      appendLog("data", `备份完成：${request.targetPath}`);
    });
  });

  ipcMain.handle(IpcChannels.restoreData, async (_event, request: RestoreDataRequest): Promise<void> => {
    const config = await readDesktopConfig();
    const instance = config?.instances.find((item) => item.id === request.instanceId);
    if (!instance) throw new Error("实例不存在");
    await withBackendRestart(request.instanceId, async () => {
      const emitProgress = (event: DataProgressEvent) =>
        context.shellWindow()?.webContents.send(IpcChannels.dataProgress, event);
      appendLog("data", `开始从备份还原数据：${request.sourcePath} -> ${resolveDataDir(instance)}`);
      await restoreDataDir(request.sourcePath, resolveDataDir(instance), (message) => appendLog("data", message), (phase, progress) =>
        emitProgress({ operation: "restore", phase, progress }),
      );
      appendLog("data", `数据还原完成：${resolveDataDir(instance)}`);
    });
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
      const previousConfig = await readDesktopConfig();
      const existingInstance = findLocalInstanceByInstallDir(previousConfig, request.installDir);
      const { handle: backend, maintenanceError } = await startLocalBackendFromInstall(
        request.installDir,
        startupProgress,
        controller.signal,
        existingInstance ? resolveDataDir(existingInstance) : undefined,
      );
      context.setBackend(backend);
      context.setBackendBaseUrl(backend.baseUrl);
      await pendingZoomSave;
      const instance: DesktopInstance = existingInstance ?? {
        id: createInstanceId(),
        name: "Local",
        mode: "local",
        remoteUrl: null,
        autoStartLocal: true,
        installDir: request.installDir,
        dataDir: null,
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
      return maintenanceError;
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
