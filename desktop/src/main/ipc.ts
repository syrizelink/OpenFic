import { app, dialog, ipcMain, session, shell, webContents, type BrowserWindow } from "electron";
import path from "node:path";
import {
  IpcChannels,
  type BackupDataRequest,
  type DataProgressEvent,
  type DeleteInstanceRequest,
  type DeleteInstanceResult,
  type EnsureInstanceSessionRequest,
  type GetDataInfoRequest,
  type GetInstanceDeletionInfoRequest,
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
  type ReportErrorPayload,
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
import { getDefaultInstallDir, resolveRuntimeDir } from "./runtime/python.js";
import { INSTANCE_DATA_ENTRIES } from "./runtime/tar-extract.js";
import { getDefaultDataDir, normalizeDataDir, resolveDataDir } from "./data-location.js";
import {
  arePathsEqual,
  backupDataDir,
  doPathsOverlap,
  inspectDataDir,
  isPathWithin,
  migrateDataDir,
  removeDataDir,
  restoreDataDir,
} from "./data-manager.js";
import { cancelUpdateDownload, checkForUpdates, downloadUpdate, getUpdateState, installUpdate, openUpdateRelease } from "./updater.js";
import { createStartupProgressTracker, getStartupProgress } from "./startup-progress.js";
import { appendLog, exportLogs } from "./logging.js";
import { captureException } from "./telemetry.js";
import type { BackendProcessHandle } from "./process.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

const PROJECT_HOME_URL = "https://github.com/syrizelink/OpenFic";
const BUG_REPORT_URL = `${PROJECT_HOME_URL}/issues/new?template=bug-report.yml`;
const FEATURE_SUGGESTION_URL = `${PROJECT_HOME_URL}/issues/new?template=feature-request.yml`;
const MIN_ZOOM_FACTOR = 0.7;
const MAX_ZOOM_FACTOR = 2.0;
const DEFAULT_ZOOM_FACTOR = 1.1;

interface LocalInstanceDeletionPaths {
  dataDir: string;
  runtimeDir: string;
}

function normalizeZoomFactor(zoomFactor: number): number {
  const clampedZoomFactor = Math.min(MAX_ZOOM_FACTOR, Math.max(MIN_ZOOM_FACTOR, zoomFactor));
  return Math.round(clampedZoomFactor * 10) / 10;
}

function getLocalInstanceDeletionPaths(instance: DesktopInstance): LocalInstanceDeletionPaths {
  const installDir = instance.installDir ?? getDefaultInstallDir();
  const dataDir = resolveDataDir(instance);
  if (!path.isAbsolute(installDir) || !path.isAbsolute(dataDir)) {
    throw new Error("实例目录必须是绝对路径");
  }
  return {
    dataDir: path.resolve(dataDir),
    runtimeDir: path.resolve(resolveRuntimeDir(installDir)),
  };
}

async function isDataDirShared(
  config: DesktopConfig,
  instance: DesktopInstance,
  instancePaths: LocalInstanceDeletionPaths,
): Promise<boolean> {
  for (const candidate of config.instances) {
    if (candidate.id === instance.id || candidate.mode !== "local") continue;
    const candidatePaths = getLocalInstanceDeletionPaths(candidate);
    if (
      await doPathsOverlap(instancePaths.dataDir, candidatePaths.dataDir) ||
      await doPathsOverlap(instancePaths.dataDir, candidatePaths.runtimeDir)
    ) return true;
  }
  return false;
}

async function isRuntimeDirShared(
  config: DesktopConfig,
  instance: DesktopInstance,
  instancePaths: LocalInstanceDeletionPaths,
): Promise<boolean> {
  for (const candidate of config.instances) {
    if (candidate.id === instance.id || candidate.mode !== "local") continue;
    const candidatePaths = getLocalInstanceDeletionPaths(candidate);
    if (
      await doPathsOverlap(instancePaths.runtimeDir, candidatePaths.runtimeDir) ||
      await doPathsOverlap(instancePaths.runtimeDir, candidatePaths.dataDir)
    ) return true;
  }
  return false;
}

async function assertSafeRuntimeDataPaths(instancePaths: LocalInstanceDeletionPaths): Promise<void> {
  const isDefaultDataDir = await arePathsEqual(instancePaths.dataDir, getDefaultDataDir());
  const pathsOverlap = await doPathsOverlap(instancePaths.runtimeDir, instancePaths.dataDir);
  const runtimeIsWithinData = await isPathWithin(instancePaths.dataDir, instancePaths.runtimeDir);
  if (pathsOverlap && (!isDefaultDataDir || !runtimeIsWithinData)) {
    throw new Error("实例的运行环境目录与数据目录重叠，无法安全删除");
  }
}

async function removeInstanceResources(
  instancePaths: LocalInstanceDeletionPaths,
  deleteData: boolean,
  runtimeDirShared: boolean,
): Promise<void> {
  const isDefaultDataDir = await arePathsEqual(instancePaths.dataDir, getDefaultDataDir());
  await assertSafeRuntimeDataPaths(instancePaths);

  const pathsToRemove: string[] = [];
  if (!runtimeDirShared) {
    pathsToRemove.push(instancePaths.runtimeDir);
  }

  if (deleteData) {
    if (isDefaultDataDir) {
      pathsToRemove.push(...[...INSTANCE_DATA_ENTRIES].map((entry) => path.join(instancePaths.dataDir, entry)));
    } else {
      pathsToRemove.push(instancePaths.dataDir);
    }
  }

  let firstError: unknown = null;
  for (const filePath of pathsToRemove) {
    try {
      await removeDataDir(filePath);
    } catch (error) {
      appendLog("instance", `清理实例资源失败：${filePath}：${error instanceof Error ? error.message : String(error)}`);
      firstError ??= error;
    }
  }
  if (firstError) throw firstError;
}

function getNextActiveInstanceId(config: DesktopConfig, remainingInstances: DesktopInstance[]): string | null {
  if (config.activeInstanceId && remainingInstances.some((instance) => instance.id === config.activeInstanceId)) {
    return config.activeInstanceId;
  }
  return remainingInstances.find((instance) => instance.favorite)?.id ?? remainingInstances[0]?.id ?? null;
}

export interface IpcContext {
  shellWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  setLogsDir: (dataDir: string | null) => void;
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

async function clearInstanceSession(instanceId: string): Promise<void> {
  const targetSession = session.fromPartition(`persist:openfic-${instanceId}`);
  await targetSession.clearStorageData();
  await targetSession.clearAuthCache();
  await targetSession.clearCache();
  await targetSession.closeAllConnections();
}

export function registerIpc(context: IpcContext): void {
  let pendingConfigMutation: Promise<void> = Promise.resolve();

  function enqueueConfigMutation<T>(operation: () => Promise<T>): Promise<T> {
    const next = pendingConfigMutation.then(operation);
    pendingConfigMutation = next.then(
      () => undefined,
      () => undefined,
    );
    return next;
  }

  async function withBackendRestart<T>(instanceId: string, operation: () => Promise<T>): Promise<T> {
    await waitForInstanceWebViews(instanceId);
    const wasRunning = context.isBackendRunning();
    if (wasRunning) await context.stopActiveBackend();
    return operation();
  }

  const saveZoomFactor = async (zoomFactor: number): Promise<number> => {
    const clampedZoomFactor = normalizeZoomFactor(zoomFactor);
    const config = await readDesktopConfig();
    await writeDesktopConfig({ ...(config ?? createDefaultConfig()), zoomFactor: clampedZoomFactor });
    context.shellWindow()?.webContents.send(IpcChannels.zoomFactorChanged, clampedZoomFactor);
    return clampedZoomFactor;
  };

  ipcMain.handle(IpcChannels.getConfig, () => readDesktopConfig());

  ipcMain.handle(IpcChannels.saveConfig, (_event, request: SaveConfigRequest) => enqueueConfigMutation(async () => {
    const previousConfig = await readDesktopConfig();
    const nextConfig = { ...request.config, zoomFactor: previousConfig?.zoomFactor };
    await writeDesktopConfig(nextConfig);
    context.onConfigSaved(nextConfig);
  }));

  ipcMain.handle(IpcChannels.getZoomFactor, async () => {
    await pendingConfigMutation;
    return normalizeZoomFactor((await readDesktopConfig())?.zoomFactor ?? DEFAULT_ZOOM_FACTOR);
  });

  ipcMain.handle(IpcChannels.saveZoomFactor, (_event, request: SaveZoomFactorRequest) => {
    if (!Number.isFinite(request.zoomFactor)) return;
    return enqueueConfigMutation(() => saveZoomFactor(request.zoomFactor));
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

  ipcMain.on(IpcChannels.reportError, (_event, payload: ReportErrorPayload) => {
    if (!payload || typeof payload.message !== "string") return;
    const error = new Error(payload.message);
    error.name = typeof payload.name === "string" ? payload.name : "Error";
    if (typeof payload.stack === "string") error.stack = payload.stack;
    captureException(error, { source: "shell-ui" });
  });

  ipcMain.handle(IpcChannels.ensureInstanceSession, (_event, request: EnsureInstanceSessionRequest) => {
    return ensureAppProtocolForPartition(request.partition);
  });

  ipcMain.handle(IpcChannels.getDefaultInstallDir, () => getDefaultInstallDir());

  ipcMain.handle(IpcChannels.getInstanceDeletionInfo, async (_event, request: GetInstanceDeletionInfoRequest) => {
    if (typeof request?.instanceId !== "string") throw new Error("无效的实例标识");
    const config = await readDesktopConfig();
    if (!config) throw new Error("未找到 OpenFic 实例配置");
    const instance = config.instances.find((item) => item.id === request.instanceId);
    if (!instance) throw new Error("实例不存在");
    if (instance.mode !== "local") {
      return { dataDir: null, dataDirShared: false, runtimeDir: null, runtimeDirShared: false };
    }
    const instancePaths = getLocalInstanceDeletionPaths(instance);
    const [dataDirShared, runtimeDirShared] = await Promise.all([
      isDataDirShared(config, instance, instancePaths),
      isRuntimeDirShared(config, instance, instancePaths),
    ]);
    return {
      dataDir: instancePaths.dataDir,
      dataDirShared,
      runtimeDir: instancePaths.runtimeDir,
      runtimeDirShared,
    };
  });

  ipcMain.handle(
    IpcChannels.deleteInstance,
    (_event, request: DeleteInstanceRequest) => enqueueConfigMutation(async (): Promise<DeleteInstanceResult> => {
      if (typeof request?.instanceId !== "string" || typeof request.deleteData !== "boolean") {
        throw new Error("无效的实例删除请求");
      }
      const config = await readDesktopConfig();
      if (!config) throw new Error("未找到 OpenFic 实例配置");
      const instance = config.instances.find((item) => item.id === request.instanceId);
      if (!instance) throw new Error("实例不存在");
      const instancePaths = instance.mode === "local" ? getLocalInstanceDeletionPaths(instance) : null;
      const dataDirShared = instancePaths ? await isDataDirShared(config, instance, instancePaths) : false;
      if (request.deleteData && dataDirShared) throw new Error("该数据目录正在被多个本地实例使用，无法清除");
      const runtimeDirShared = instancePaths
        ? await isRuntimeDirShared(config, instance, instancePaths)
        : false;

      appendLog("instance", `准备删除实例：${instance.name}（${instance.id}）`);
      const remainingInstances = config.instances.filter((item) => item.id !== instance.id);
      const nextActiveInstanceId = getNextActiveInstanceId(config, remainingInstances);
      await waitForInstanceWebViews(instance.id);
      if (config.activeInstanceId === instance.id) {
        await context.stopActiveBackend();
        context.setLogsDir(null);
      }
      await clearInstanceSession(instance.id);

      const nextConfig: DesktopConfig = {
        ...config,
        activeInstanceId: nextActiveInstanceId,
        instances: remainingInstances,
      };
      await writeDesktopConfig(nextConfig);
      context.onConfigSaved(nextConfig);
      if (instancePaths) {
        if (runtimeDirShared) {
          appendLog("instance", `保留共享运行环境：${instancePaths.runtimeDir}`);
        }
        try {
          await removeInstanceResources(instancePaths, request.deleteData, runtimeDirShared);
        } catch (error) {
          appendLog("instance", `实例资源清理未完成：${error instanceof Error ? error.message : String(error)}`);
        }
      }
      return { nextActiveInstanceId };
    }),
  );

  ipcMain.handle(IpcChannels.switchInstance, (_event, request: SwitchInstanceRequest) =>
    enqueueConfigMutation(() => context.switchInstance(request.instanceId)),
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

  ipcMain.handle(IpcChannels.migrateData, (_event, request: MigrateDataRequest) =>
    enqueueConfigMutation(async (): Promise<MigrateDataResult> => {
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
    }),
  );

  ipcMain.handle(IpcChannels.backupData, (_event, request: BackupDataRequest) =>
    enqueueConfigMutation(async (): Promise<void> => {
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
    }),
  );

  ipcMain.handle(IpcChannels.restoreData, (_event, request: RestoreDataRequest) =>
    enqueueConfigMutation(async (): Promise<void> => {
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
    }),
  );

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

  ipcMain.handle(IpcChannels.installRuntime, (_event, request: InstallRuntimeRequest) =>
    enqueueConfigMutation(async () => {
      const window = context.shellWindow();
      if (!window) throw new Error("shell window is not available");
      await installLocalRuntime(window.webContents, request.installDir);
    }),
  );

  ipcMain.handle(IpcChannels.startLocalBackend, (_event, request: StartLocalBackendRequest) =>
    enqueueConfigMutation(async () => {
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
          existingInstance ? resolveDataDir(existingInstance) : request.dataDir ?? undefined,
        );
        context.setBackend(backend);
        context.setBackendBaseUrl(backend.baseUrl);
        const instance: DesktopInstance = existingInstance ?? {
          id: createInstanceId(),
          name: "Local",
          mode: "local",
          remoteUrl: null,
          autoStartLocal: true,
          installDir: request.installDir,
          dataDir: normalizeDataDir(request.dataDir),
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
    }),
  );

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
