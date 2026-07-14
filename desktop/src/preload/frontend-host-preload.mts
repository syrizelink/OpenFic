import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("openficDesktopHost", {
  publishAppearance: (payload: unknown): void => {
    ipcRenderer.sendToHost("openfic:appearance", payload);
  },
});
