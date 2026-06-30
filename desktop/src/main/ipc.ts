import { ipcMain } from "electron";
import type { BrowserWindow } from "electron";
import { IpcChannels, type CheckRemoteRequest, type SaveConfigRequest } from "../shared/ipc.js";
import { readDesktopConfig, writeDesktopConfig } from "./config.js";
import { waitForBackend } from "./health.js";
import { runLocalSetup } from "./runtime/setup-runner.js";
import type { BackendProcessHandle } from "./process.js";

export interface IpcContext {
  setupWindow: () => BrowserWindow | null;
  setBackend: (handle: BackendProcessHandle) => void;
  setBackendBaseUrl: (url: string) => void;
  openMainWindow: () => void;
}

export function registerIpc(context: IpcContext): void {
  ipcMain.handle(IpcChannels.getConfig, () => readDesktopConfig());

  ipcMain.handle(IpcChannels.saveConfig, async (_event, request: SaveConfigRequest) => {
    await writeDesktopConfig(request.config);
  });

  ipcMain.handle(IpcChannels.checkRemote, async (_event, request: CheckRemoteRequest) => {
    await waitForBackend(request.url, 10_000);
  });

  ipcMain.handle(IpcChannels.runLocalSetup, async () => {
    const window = context.setupWindow();
    if (!window) throw new Error("setup window is not available");
    const backend = await runLocalSetup(window.webContents);
    context.setBackend(backend);
    context.setBackendBaseUrl(backend.baseUrl);
  });

  ipcMain.handle(IpcChannels.closeSetup, () => {
    context.setupWindow()?.close();
    context.openMainWindow();
  });
}
