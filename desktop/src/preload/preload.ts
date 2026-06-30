import {
  IpcChannels,
  type CheckRemoteRequest,
  type InitializeAppResult,
  type SaveConfigRequest,
  type SetupProgressEvent,
} from "../shared/ipc.js";
import type { DesktopConfig } from "../shared/config.js";
import path from "node:path";

const electron = require("electron") as typeof import("electron");

const { contextBridge, ipcRenderer } = electron;

const desktopApi = {
  getConfig: (): Promise<DesktopConfig | null> => ipcRenderer.invoke(IpcChannels.getConfig),
  saveConfig: (config: DesktopConfig): Promise<void> => ipcRenderer.invoke(IpcChannels.saveConfig, { config } satisfies SaveConfigRequest),
  initializeApp: (): Promise<InitializeAppResult> => ipcRenderer.invoke(IpcChannels.initializeApp),
  runLocalSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.runLocalSetup),
  checkRemote: (url: string): Promise<void> => ipcRenderer.invoke(IpcChannels.checkRemote, { url } satisfies CheckRemoteRequest),
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
