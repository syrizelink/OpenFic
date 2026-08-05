import { BrowserWindow, screen, shell } from "electron";
import { fileURLToPath } from "node:url";
import { readWindowState, saveWindowStateSync, type WindowState } from "./window-state.js";
import { appendLog } from "./logging.js";

const preloadPath = fileURLToPath(new URL("../preload/preload.mjs", import.meta.url));

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 800;
const MIN_WIDTH = 960;
const MIN_HEIGHT = 640;
const SAVE_DEBOUNCE_MS = 500;
const WINDOW_SHOW_FALLBACK_MS = 600;

function writeWindowLog(message: string): void {
  appendLog("startup", message);
}

function attachWindowDiagnostics(window: BrowserWindow, name: string): void {
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

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface WindowLayout {
  width: number;
  height: number;
  x?: number;
  y?: number;
  isMaximized: boolean;
  needsCenter: boolean;
}

function isBoundsVisible(bounds: Rect): boolean {
  return screen.getAllDisplays().some((display) => {
    const displayBounds = display.bounds;
    return (
      bounds.x < displayBounds.x + displayBounds.width &&
      bounds.x + bounds.width > displayBounds.x &&
      bounds.y < displayBounds.y + displayBounds.height &&
      bounds.y + bounds.height > displayBounds.y
    );
  });
}

function resolveWindowLayout(state: WindowState | null): WindowLayout {
  if (
    state &&
    state.width >= MIN_WIDTH &&
    state.height >= MIN_HEIGHT &&
    isBoundsVisible(state)
  ) {
    return {
      width: state.width,
      height: state.height,
      x: state.x,
      y: state.y,
      isMaximized: state.isMaximized,
      needsCenter: false,
    };
  }
  return {
    width: DEFAULT_WIDTH,
    height: DEFAULT_HEIGHT,
    isMaximized: false,
    needsCenter: true,
  };
}

function readNormalBounds(window: BrowserWindow): Rect {
  const [x, y] = window.getPosition();
  const [width, height] = window.getSize();
  return { x, y, width, height };
}

function attachWindowStateTracking(window: BrowserWindow): void {
  let normalBounds = readNormalBounds(window);
  let saveTimer: ReturnType<typeof setTimeout> | null = null;

  const captureNormalBounds = (): void => {
    if (window.isMaximized()) return;
    normalBounds = readNormalBounds(window);
  };

  const scheduleSave = (): void => {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveTimer = null;
      saveWindowStateSync({ ...normalBounds, isMaximized: window.isMaximized() });
    }, SAVE_DEBOUNCE_MS);
  };

  window.on("resize", () => {
    captureNormalBounds();
    scheduleSave();
  });
  window.on("move", () => {
    captureNormalBounds();
    scheduleSave();
  });
  window.on("maximize", () => scheduleSave());
  window.on("unmaximize", () => {
    captureNormalBounds();
    scheduleSave();
  });
  window.on("close", () => {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    saveWindowStateSync({ ...normalBounds, isMaximized: window.isMaximized() });
  });
}

export function loadMainApp(window: BrowserWindow): void {
  void window.loadURL("app://setup/ui.html");
}

export function createMainWindow(): BrowserWindow {
  const layout = resolveWindowLayout(readWindowState());
  const options: Electron.BrowserWindowConstructorOptions = {
    width: layout.width,
    height: layout.height,
    frame: false,
    show: false,
    backgroundColor: "#ffffff",
    titleBarStyle: "hidden",
    webPreferences: {
      contextIsolation: true,
      sandbox: false,
      webviewTag: true,
      preload: preloadPath,
    },
  };
  if (layout.x !== undefined && layout.y !== undefined) {
    options.x = layout.x;
    options.y = layout.y;
  }

  const window = new BrowserWindow(options);

  window.setResizable(true);
  window.setMinimumSize(MIN_WIDTH, MIN_HEIGHT);
  if (layout.needsCenter) window.center();

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  attachWindowDiagnostics(window, "main");

  let showTimer: ReturnType<typeof setTimeout> | null = null;
  let hasShown = false;
  const showWindow = () => {
    if (window.isDestroyed() || hasShown) return;

    hasShown = true;
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
    if (layout.isMaximized) window.maximize();
    window.show();
  };

  window.once("ready-to-show", () => {
    showWindow();
  });
  window.once("closed", () => {
    if (showTimer) clearTimeout(showTimer);
  });

  attachWindowStateTracking(window);

  loadMainApp(window);
  showTimer = setTimeout(showWindow, WINDOW_SHOW_FALLBACK_MS);
  return window;
}
