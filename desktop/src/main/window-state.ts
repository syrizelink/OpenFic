import { app } from "electron";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

export interface WindowState {
  x: number;
  y: number;
  width: number;
  height: number;
  isMaximized: boolean;
}

function getWindowStatePath(): string {
  return path.join(app.getPath("userData"), "window-state.json");
}

function isWindowState(value: unknown): value is WindowState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<WindowState>;
  return (
    typeof candidate.x === "number" &&
    Number.isFinite(candidate.x) &&
    typeof candidate.y === "number" &&
    Number.isFinite(candidate.y) &&
    typeof candidate.width === "number" &&
    Number.isFinite(candidate.width) &&
    candidate.width > 0 &&
    typeof candidate.height === "number" &&
    Number.isFinite(candidate.height) &&
    candidate.height > 0 &&
    typeof candidate.isMaximized === "boolean"
  );
}

export function readWindowState(): WindowState | null {
  try {
    const raw = readFileSync(getWindowStatePath(), "utf-8");
    const parsed = JSON.parse(raw) as unknown;
    return isWindowState(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveWindowStateSync(state: WindowState): void {
  try {
    const filePath = getWindowStatePath();
    mkdirSync(path.dirname(filePath), { recursive: true });
    writeFileSync(filePath, JSON.stringify(state, null, 2), "utf-8");
  } catch {
    // Window state persistence must never block app shutdown.
  }
}
