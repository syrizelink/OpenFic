import { dialog, ipcMain, type BrowserWindow } from "electron";
import {
  IpcChannels,
  type CheckRemoteRequest,
  type EnsureInstanceSessionRequest,
  type InitializeAppResult,
  type InspectLocalRuntimeRequest,
  type InspectLocalRuntimeResult,
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
import { findLocalInstanceByInstallDir, normalizeInstallDir } from "./local-instance.js";
import { inspectLocalRuntime, installLocalRuntime, startLocalBackendFromInstall } from "./runtime/setup-runner.js";
import { getDefaultInstallDir } from "./runtime/python.js";
import { cancelUpdateDownload, checkForUpdates, downloadUpdate, getUpdateState, installUpdate, openUpdateRelease } from "./updater.js";
import { createStartupProgressTracker, getStartupProgress } from "./startup-progress.js";
import type { BackendProcessHandle } from "./process.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

export interface IpcContext {
  shellWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  initializeApp: () => Promise<InitializeAppResult>;
  switchInstance: (instanceId: string) => Promise<InitializeAppResult>;
  pingInstance: (instance: DesktopInstance) => Promise<number>;
  onConfigSaved: (config: DesktopConfig) => void;
}

function createInstanceId(): string {
  return `instance-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function registerIpc(context: IpcContext): void {
  ipcMain.handle(IpcChannels.getConfig, () => readDesktopConfig());

  ipcMain.handle(IpcChannels.saveConfig, async (_event, request: SaveConfigRequest) => {
    await writeDesktopConfig(request.config);
    context.onConfigSaved(request.config);
  });

  ipcMain.handle(IpcChannels.initializeApp, () => context.initializeApp());
  ipcMain.handle(IpcChannels.getStartupProgress, () => getStartupProgress());
  ipcMain.handle(IpcChannels.getUpdateState, () => getUpdateState());
  ipcMain.handle(IpcChannels.checkForUpdate, () => checkForUpdates());
  ipcMain.handle(IpcChannels.downloadUpdate, () => downloadUpdate());
  ipcMain.handle(IpcChannels.cancelUpdateDownload, () => cancelUpdateDownload());
  ipcMain.handle(IpcChannels.installUpdate, () => installUpdate());
  ipcMain.handle(IpcChannels.openUpdateRelease, () => openUpdateRelease());

  ipcMain.handle(IpcChannels.ensureInstanceSession, (_event, request: EnsureInstanceSessionRequest) => {
    return ensureAppProtocolForPartition(request.partition);
  });

  ipcMain.handle(IpcChannels.getDefaultInstallDir, () => getDefaultInstallDir());

  ipcMain.handle(IpcChannels.checkRemote, async (_event, request: CheckRemoteRequest) => {
    const startupProgress = createStartupProgressTracker((progress) => {
      _event.sender.send(IpcChannels.startupProgress, progress);
    });
    startupProgress.begin({
      step: "connect-remote",
      title: "连接 OpenFic 服务",
      message: `正在连接 ${request.url}`,
      progress: 0.3,
    });
    try {
      await waitForBackend(request.url, 10_000);
      startupProgress.begin({
        step: "verify-remote",
        title: "验证服务状态",
        message: "远程服务已响应",
        progress: 0.7,
      });
      startupProgress.complete();
    } catch (error) {
      startupProgress.fail(error);
      throw error;
    }
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
    const startupProgress = createStartupProgressTracker((progress) => {
      window.webContents.send(IpcChannels.startupProgress, progress);
    });
    try {
      const backend = await startLocalBackendFromInstall(request.installDir, startupProgress);
      context.setBackend(backend);
      context.setBackendBaseUrl(backend.baseUrl);
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
      startupProgress.fail(error);
      throw error;
    }
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
