import { IpcChannels, type CheckRemoteRequest, type SaveConfigRequest, type SetupProgressEvent } from "../shared/ipc.js";
import type { DesktopConfig } from "../shared/config.js";

const electron = require("electron") as typeof import("electron");

const { contextBridge, ipcRenderer } = electron;

const desktopApi = {
  getConfig: (): Promise<DesktopConfig | null> => ipcRenderer.invoke(IpcChannels.getConfig),
  saveConfig: (config: DesktopConfig): Promise<void> => ipcRenderer.invoke(IpcChannels.saveConfig, { config } satisfies SaveConfigRequest),
  runLocalSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.runLocalSetup),
  checkRemote: (url: string): Promise<void> => ipcRenderer.invoke(IpcChannels.checkRemote, { url } satisfies CheckRemoteRequest),
  closeSetup: (): Promise<void> => ipcRenderer.invoke(IpcChannels.closeSetup),
  onSetupProgress: (handler: (event: SetupProgressEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: SetupProgressEvent) => handler(payload);
    ipcRenderer.on(IpcChannels.setupProgress, listener);
    return () => ipcRenderer.off(IpcChannels.setupProgress, listener);
  },
};

contextBridge.exposeInMainWorld("openficDesktop", desktopApi);
