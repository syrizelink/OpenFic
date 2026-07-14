import { contextBridge, ipcRenderer } from "electron";
import { fileURLToPath } from "node:url";
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
  type SetupProgressEvent,
  type StartupProgressEvent,
  type StartLocalBackendRequest,
  type SwitchInstanceRequest,
  type UpdateState,
} from "../shared/ipc.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";

const desktopApi = {
  getConfig: (): Promise<DesktopConfig | null> => ipcRenderer.invoke(IpcChannels.getConfig),
  saveConfig: (config: DesktopConfig): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.saveConfig, { config } satisfies SaveConfigRequest),
  initializeApp: (): Promise<InitializeAppResult> => ipcRenderer.invoke(IpcChannels.initializeApp),
  ensureInstanceSession: (partition: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.ensureInstanceSession, { partition } satisfies EnsureInstanceSessionRequest),
  getDefaultInstallDir: (): Promise<string> => ipcRenderer.invoke(IpcChannels.getDefaultInstallDir),
  installRuntime: (installDir: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.installRuntime, { installDir } satisfies InstallRuntimeRequest),
  startLocalBackend: (installDir: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.startLocalBackend, { installDir } satisfies StartLocalBackendRequest),
  checkRemote: (url: string): Promise<void> =>
    ipcRenderer.invoke(IpcChannels.checkRemote, { url } satisfies CheckRemoteRequest),
  switchInstance: (instanceId: string): Promise<InitializeAppResult> =>
    ipcRenderer.invoke(IpcChannels.switchInstance, { instanceId } satisfies SwitchInstanceRequest),
  pingInstance: (instance: DesktopInstance): Promise<PingInstanceResult> =>
    ipcRenderer.invoke(IpcChannels.pingInstance, { instance } satisfies PingInstanceRequest),
  selectDirectory: (): Promise<string | null> => ipcRenderer.invoke(IpcChannels.selectDirectory),
  inspectLocalRuntime: (installDir: string): Promise<InspectLocalRuntimeResult> =>
    ipcRenderer.invoke(IpcChannels.inspectLocalRuntime, { installDir } satisfies InspectLocalRuntimeRequest),
  closeSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.closeSetup),
  showSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.showSetup),
  frontendHostPreloadPath: fileURLToPath(new URL("./frontend-host-preload.mjs", import.meta.url)),
  minimizeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.minimizeWindow),
  toggleMaximizeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.toggleMaximizeWindow),
  closeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.closeWindow),
  getUpdateState: (): Promise<UpdateState> => ipcRenderer.invoke(IpcChannels.getUpdateState),
  getStartupProgress: (): Promise<StartupProgressEvent | null> => ipcRenderer.invoke(IpcChannels.getStartupProgress),
  checkForUpdate: (): Promise<void> => ipcRenderer.invoke(IpcChannels.checkForUpdate),
  downloadUpdate: (): Promise<void> => ipcRenderer.invoke(IpcChannels.downloadUpdate),
  cancelUpdateDownload: (): Promise<void> => ipcRenderer.invoke(IpcChannels.cancelUpdateDownload),
  installUpdate: (): Promise<void> => ipcRenderer.invoke(IpcChannels.installUpdate),
  openUpdateRelease: (): Promise<void> => ipcRenderer.invoke(IpcChannels.openUpdateRelease),
  onSetupProgress: (handler: (event: SetupProgressEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: SetupProgressEvent) => handler(payload);
    ipcRenderer.on(IpcChannels.setupProgress, listener);
    return () => ipcRenderer.off(IpcChannels.setupProgress, listener);
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
