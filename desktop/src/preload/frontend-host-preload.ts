const electron = require("electron") as typeof import("electron");

const { contextBridge, ipcRenderer } = electron;

contextBridge.exposeInMainWorld("openficDesktopHost", {
  publishAppearance: (payload: unknown): void => {
    ipcRenderer.sendToHost("openfic:appearance", payload);
  },
});
