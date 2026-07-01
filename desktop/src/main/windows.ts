import type { BrowserWindow as BrowserWindowType } from "electron";
import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";

const electron = require("electron") as typeof import("electron");

const { app, BrowserWindow, shell } = electron;

function writeWindowLog(message: string): void {
  try {
    const logDir = path.join(process.env.APPDATA ?? app.getPath("userData"), "openfic-desktop");
    mkdirSync(logDir, { recursive: true });
    appendFileSync(path.join(logDir, "startup.log"), `[${new Date().toISOString()}] ${message}\n`, "utf8");
  } catch {
    // Ignore diagnostics logging failures.
  }
}

function attachWindowDiagnostics(window: BrowserWindowType, name: string): void {
  window.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    writeWindowLog(`${name} did-fail-load code=${errorCode} url=${validatedURL} error=${errorDescription}`);
  });

  window.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    writeWindowLog(`${name} console level=${level} source=${sourceId}:${line} message=${message}`);
  });

  window.webContents.on("render-process-gone", (_event, details) => {
    writeWindowLog(`${name} render-process-gone reason=${details.reason} exitCode=${details.exitCode}`);
  });

  window.webContents.on("did-finish-load", () => {
    writeWindowLog(`${name} did-finish-load url=${window.webContents.getURL()}`);
  });
}

function applyShellWindowPresentation(window: BrowserWindowType): void {
  window.setResizable(true);
  window.setMinimumSize(960, 640);
  window.setSize(1280, 800);
  window.center();
}

export function loadMainApp(window: BrowserWindowType): void {
  applyShellWindowPresentation(window);
  void window.loadURL("app://setup/ui.html");
}

export function createMainWindow(): BrowserWindowType {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    frame: false,
    show: false,
    titleBarStyle: "hidden",
    webPreferences: {
      contextIsolation: true,
      sandbox: false,
      webviewTag: true,
      preload: path.join(__dirname, "..", "preload", "preload.js"),
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  attachWindowDiagnostics(window, "main");

  window.once("ready-to-show", () => window.show());
  loadMainApp(window);
  return window;
}
