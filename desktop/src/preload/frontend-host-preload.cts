const { contextBridge, ipcRenderer } = require("electron") as typeof import("electron");

contextBridge.exposeInMainWorld("openficDesktopHost", {
  publishAppearance: (payload: unknown): void => {
    ipcRenderer.sendToHost("openfic:appearance", payload);
  },
});
