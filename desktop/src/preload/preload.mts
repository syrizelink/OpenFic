import { contextBridge, ipcRenderer, webFrame } from "electron";
import {
  IpcChannels,
  type BackupDataRequest,
  type DataInfo,
  type DataProgressEvent,
  type DeleteInstanceRequest,
  type DeleteInstanceResult,
  type EnsureInstanceSessionRequest,
  type GetDataInfoRequest,
  type GetInstanceDeletionInfoRequest,
  type InitializeAppResult,
  type InspectDataDirRequest,
  type InspectDataDirResult,
  type InspectLocalRuntimeRequest,
  type InspectLocalRuntimeResult,
  type InstallRuntimeRequest,
  type InstanceDeletionInfo,
  type LogFrontendDiagnosticRequest,
  type MigrateDataRequest,
  type MigrateDataResult,
  type PingInstanceRequest,
  type PingInstanceResult,
  type ReportErrorPayload,
  type RestoreDataRequest,
  type SaveConfigRequest,
  type SaveZoomFactorRequest,
  type SetupProgressEvent,
  type StartupProgressEvent,
  type StartLocalBackendRequest,
  type SwitchInstanceRequest,
  type UpdateState,
} from "../shared/ipc.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";
import { getFrontendHostPreloadPath } from "./frontend-host-preload-path.mjs";

const MIN_ZOOM_FACTOR = 0.7;
const MAX_ZOOM_FACTOR = 2.0;
const ZOOM_STEP = 0.1;

function clampZoomFactor(zoomFactor: number): number {
  return Math.round(Math.min(MAX_ZOOM_FACTOR, Math.max(MIN_ZOOM_FACTOR, zoomFactor)) * 10) / 10;
}

function applyZoomFactor(zoomFactor: number, shouldSave: boolean): void {
  const nextZoomFactor = clampZoomFactor(zoomFactor);
  webFrame.setZoomFactor(nextZoomFactor);
  if (shouldSave) {
    void ipcRenderer.invoke(IpcChannels.saveZoomFactor, { zoomFactor: nextZoomFactor } satisfies SaveZoomFactorRequest);
  }
}

function enableCtrlWheelZoom(): void {
  void ipcRenderer.invoke(IpcChannels.getZoomFactor).then((zoomFactor: unknown) => {
    if (typeof zoomFactor !== "number" || !Number.isFinite(zoomFactor)) return;
    applyZoomFactor(zoomFactor, false);
  });
  window.addEventListener(
    "wheel",
    (event) => {
      if (!event.ctrlKey || event.deltaY === 0) return;
      event.preventDefault();
      applyZoomFactor(webFrame.getZoomFactor() + (event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP), true);
    },
    { capture: true, passive: false },
  );
}

enableCtrlWheelZoom();

ipcRenderer.on(IpcChannels.zoomFactorChanged, (_event, zoomFactor: unknown) => {
  if (typeof zoomFactor !== "number" || !Number.isFinite(zoomFactor)) return;
  applyZoomFactor(zoomFactor, false);
});

const desktopApi = {
  getConfig: (): Promise<DesktopConfig | null> => ipcRenderer.invoke(IpcChannels.getConfig),
  saveConfig: (config: DesktopConfig): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.saveConfig, { config } satisfies SaveConfigRequest),
  initializeApp: (): Promise<InitializeAppResult> => ipcRenderer.invoke(IpcChannels.initializeApp),
  cancelStartup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.cancelStartup),
  ensureInstanceSession: (partition: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.ensureInstanceSession, { partition } satisfies EnsureInstanceSessionRequest),
  getDefaultInstallDir: (): Promise<string> => ipcRenderer.invoke(IpcChannels.getDefaultInstallDir),
  installRuntime: (installDir: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.installRuntime, { installDir } satisfies InstallRuntimeRequest),
  startLocalBackend: (installDir: string, dataDir?: string | null): Promise<string | null> =>
    ipcRenderer.invoke(IpcChannels.startLocalBackend, { installDir, dataDir } satisfies StartLocalBackendRequest),
  switchInstance: (instanceId: string): Promise<InitializeAppResult> =>
    ipcRenderer.invoke(IpcChannels.switchInstance, { instanceId } satisfies SwitchInstanceRequest),
  getInstanceDeletionInfo: (instanceId: string): Promise<InstanceDeletionInfo> =>
    ipcRenderer.invoke(IpcChannels.getInstanceDeletionInfo, { instanceId } satisfies GetInstanceDeletionInfoRequest),
  deleteInstance: (instanceId: string, deleteData: boolean): Promise<DeleteInstanceResult> =>
    ipcRenderer.invoke(IpcChannels.deleteInstance, { instanceId, deleteData } satisfies DeleteInstanceRequest),
  pingInstance: (instance: DesktopInstance): Promise<PingInstanceResult> =>
    ipcRenderer.invoke(IpcChannels.pingInstance, { instance } satisfies PingInstanceRequest),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke(IpcChannels.selectDirectory),
  selectSaveFile: (): Promise<string | null> => ipcRenderer.invoke(IpcChannels.selectSaveFile),
  selectOpenFile: (): Promise<string | null> => ipcRenderer.invoke(IpcChannels.selectOpenFile),
  getDefaultDataDir: (): Promise<string> => ipcRenderer.invoke(IpcChannels.getDefaultDataDir),
  getDataInfo: (instanceId: string): Promise<DataInfo> =>
    ipcRenderer.invoke(IpcChannels.getDataInfo, { instanceId } satisfies GetDataInfoRequest),
  inspectDataDir: (dataDir: string): Promise<InspectDataDirResult> =>
    ipcRenderer.invoke(IpcChannels.inspectDataDir, { dataDir } satisfies InspectDataDirRequest),
  migrateData: (instanceId: string, newDataDir: string, deleteOldDir: boolean): Promise<MigrateDataResult> =>
    ipcRenderer.invoke(IpcChannels.migrateData, { instanceId, newDataDir, deleteOldDir } satisfies MigrateDataRequest),
  backupData: (instanceId: string, targetPath: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.backupData, { instanceId, targetPath } satisfies BackupDataRequest),
  restoreData: (instanceId: string, sourcePath: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.restoreData, { instanceId, sourcePath } satisfies RestoreDataRequest),
  inspectLocalRuntime: (installDir: string): Promise<InspectLocalRuntimeResult> =>
    ipcRenderer.invoke(IpcChannels.inspectLocalRuntime, { installDir } satisfies InspectLocalRuntimeRequest),
  frontendHostPreloadPath: getFrontendHostPreloadPath(import.meta.url),
  minimizeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.minimizeWindow),
  toggleMaximizeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.toggleMaximizeWindow),
  toggleFullScreen: (): Promise<void> => ipcRenderer.invoke(IpcChannels.toggleFullScreen),
  reloadWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.reloadWindow),
  toggleDevTools: (): Promise<void> => ipcRenderer.invoke(IpcChannels.toggleDevTools),
  closeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.closeWindow),
  getUpdateState: (): Promise<UpdateState> => ipcRenderer.invoke(IpcChannels.getUpdateState),
  getStartupProgress: (): Promise<StartupProgressEvent | null> => ipcRenderer.invoke(IpcChannels.getStartupProgress),
  checkForUpdate: (): Promise<void> => ipcRenderer.invoke(IpcChannels.checkForUpdate),
  downloadUpdate: (): Promise<void> => ipcRenderer.invoke(IpcChannels.downloadUpdate),
  cancelUpdateDownload: (): Promise<void> => ipcRenderer.invoke(IpcChannels.cancelUpdateDownload),
  installUpdate: (): Promise<void> => ipcRenderer.invoke(IpcChannels.installUpdate),
  openUpdateRelease: (): Promise<void> => ipcRenderer.invoke(IpcChannels.openUpdateRelease),
  exportLogs: (): Promise<string | null> => ipcRenderer.invoke(IpcChannels.exportLogs),
  logFrontendDiagnostic: (message: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.logFrontendDiagnostic, { message } satisfies LogFrontendDiagnosticRequest),
  reportError: (payload: ReportErrorPayload): void => ipcRenderer.send(IpcChannels.reportError, payload),
  openProjectHome: (): Promise<void> => ipcRenderer.invoke(IpcChannels.openProjectHome),
  reportBug: (): Promise<void> => ipcRenderer.invoke(IpcChannels.reportBug),
  suggestFeature: (): Promise<void> => ipcRenderer.invoke(IpcChannels.suggestFeature),
  getZoomFactor: (): Promise<number> => ipcRenderer.invoke(IpcChannels.getZoomFactor),
  saveZoomFactor: async (zoomFactor: number): Promise<void> => {
    const savedZoomFactor = await ipcRenderer.invoke(IpcChannels.saveZoomFactor, {
      zoomFactor: clampZoomFactor(zoomFactor),
    } satisfies SaveZoomFactorRequest);
    if (typeof savedZoomFactor === "number" && Number.isFinite(savedZoomFactor)) applyZoomFactor(savedZoomFactor, false);
  },
  onZoomFactorChanged: (handler: (zoomFactor: number) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, zoomFactor: unknown) => {
      if (typeof zoomFactor === "number" && Number.isFinite(zoomFactor)) handler(zoomFactor);
    };
    ipcRenderer.on(IpcChannels.zoomFactorChanged, listener);
    return () => ipcRenderer.off(IpcChannels.zoomFactorChanged, listener);
  },
  onSetupProgress: (handler: (event: SetupProgressEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: SetupProgressEvent) => handler(payload);
    ipcRenderer.on(IpcChannels.setupProgress, listener);
    return () => ipcRenderer.off(IpcChannels.setupProgress, listener);
  },
  onDataProgress: (handler: (event: DataProgressEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: DataProgressEvent) => handler(payload);
    ipcRenderer.on(IpcChannels.dataProgress, listener);
    return () => ipcRenderer.off(IpcChannels.dataProgress, listener);
  },
  onStartupProgress: (handler: (event: StartupProgressEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: StartupProgressEvent) => handler(payload);
    ipcRenderer.on(IpcChannels.startupProgress, listener);
    return () => ipcRenderer.off(IpcChannels.startupProgress, listener);
  },
  onUpdateState: (handler: (state: UpdateState) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: UpdateState) => handler(payload);
    ipcRenderer.on(IpcChannels.updateState, listener);
    return () => ipcRenderer.off(IpcChannels.updateState, listener);
  },
};

contextBridge.exposeInMainWorld("openficDesktop", desktopApi);
