const { contextBridge, ipcRenderer, webFrame } = require("electron") as typeof import("electron");

const MIN_ZOOM_FACTOR = 0.7;
const MAX_ZOOM_FACTOR = 2.0;
const ZOOM_STEP = 0.1;

function clampZoomFactor(zoomFactor: number): number {
  return Math.round(Math.min(MAX_ZOOM_FACTOR, Math.max(MIN_ZOOM_FACTOR, zoomFactor)) * 10) / 10;
}

function getMenuShortcut(event: KeyboardEvent): string | null {
  if (event.altKey && !event.ctrlKey && !event.metaKey) {
    if (event.code === "KeyW") return "menu-window";
    if (event.code === "KeyI") return "menu-instance";
    if (event.code === "KeyH") return "menu-help";
  }
  if (event.key === "F11" && !event.ctrlKey && !event.altKey && !event.metaKey) return "toggle-full-screen";
  if (event.key === "F12" && !event.ctrlKey && !event.altKey && !event.metaKey) return "toggle-dev-tools";
  if (!event.ctrlKey || event.altKey || event.metaKey) return null;
  if (event.shiftKey) {
    if (event.code === "KeyM") return "toggle-maximize";
    return null;
  }
  if (event.code === "KeyM") return "minimize-window";
  if (event.code === "Equal" || event.code === "NumpadAdd") return "zoom-in";
  if (event.code === "Minus" || event.code === "NumpadSubtract") return "zoom-out";
  if (event.code === "Digit0" || event.code === "Numpad0") return "reset-zoom";
  if (event.code === "KeyQ") return "close-window";
  return null;
}

ipcRenderer.on("openfic:zoom-factor", (_event, zoomFactor: unknown) => {
  if (typeof zoomFactor !== "number" || !Number.isFinite(zoomFactor)) return;
  webFrame.setZoomFactor(clampZoomFactor(zoomFactor));
});

window.addEventListener(
  "wheel",
  (event) => {
    if (!event.ctrlKey || event.deltaY === 0) return;
    event.preventDefault();
    const zoomFactor = clampZoomFactor(webFrame.getZoomFactor() + (event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
    webFrame.setZoomFactor(zoomFactor);
    ipcRenderer.sendToHost("openfic:zoom-factor", zoomFactor);
  },
  { capture: true, passive: false },
);

window.addEventListener(
  "keydown",
  (event) => {
    const shortcut = getMenuShortcut(event);
    if (!shortcut) return;
    event.preventDefault();
    ipcRenderer.sendToHost("openfic:menu-shortcut", shortcut);
  },
  { capture: true },
);

contextBridge.exposeInMainWorld("openficDesktopHost", {
  publishAppearance: (payload: unknown): void => {
    ipcRenderer.sendToHost("openfic:appearance", payload);
  },
  publishLanguage: (language: unknown): void => {
    ipcRenderer.sendToHost("openfic:language", language);
  },
  publishSocketDiagnostic: (payload: unknown): void => {
    ipcRenderer.sendToHost("openfic:socket-diagnostic", payload);
  },
});
