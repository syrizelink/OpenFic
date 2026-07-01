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
  type SetupProgressEvent,
  type StartLocalBackendRequest,
  type SwitchInstanceRequest,
} from "../shared/ipc.js";
import type { DesktopConfig, DesktopInstance } from "../shared/config.js";
import path from "node:path";

const electron = require("electron") as typeof import("electron");

const { contextBridge, ipcRenderer } = electron;

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
  checkDirectoryEmpty: (dirPath: string): Promise<CheckDirectoryEmptyResult> =>
    ipcRenderer.invoke(IpcChannels.checkDirectoryEmpty, { path: dirPath } satisfies CheckDirectoryEmptyRequest),
  closeSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.closeSetup),
  showSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.showSetup),
  frontendHostPreloadPath: path.join(__dirname, "frontend-host-preload.js"),
  minimizeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.minimizeWindow),
  toggleMaximizeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.toggleMaximizeWindow),
  closeWindow: (): Promise<void> => ipcRenderer.invoke(IpcChannels.closeWindow),
  onSetupProgress: (handler: (event: SetupProgressEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: SetupProgressEvent) => handler(payload);
    ipcRenderer.on(IpcChannels.setupProgress, listener);
    return () => ipcRenderer.off(IpcChannels.setupProgress, listener);
  },
};

contextBridge.exposeInMainWorld("openficDesktop", desktopApi);
