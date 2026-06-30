import { BrowserWindow, shell } from "electron";
import path from "node:path";

export function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "..", "preload", "preload.js"),
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  window.once("ready-to-show", () => window.show());
  void window.loadURL("app://openfic/");
  return window;
}

export function createSetupWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 760,
    height: 560,
    resizable: false,
    show: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "..", "preload", "preload.js"),
    },
  });

  window.once("ready-to-show", () => window.show());
  void window.loadURL("app://setup/index.html");
  return window;
}
