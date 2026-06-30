import type { DesktopConfig } from "./config.js";

export const IpcChannels = {
  getConfig: "config:get",
  saveConfig: "config:save",
  initializeApp: "app:initialize",
  runLocalSetup: "setup:run-local",
  checkRemote: "setup:check-remote",
  setupProgress: "setup:progress",
  closeSetup: "setup:close",
  showSetup: "shell:show-setup",
  minimizeWindow: "window:minimize",
  toggleMaximizeWindow: "window:toggle-maximize",
  closeWindow: "window:close",
} as const;

export interface SetupProgressEvent {
  step: "download-python" | "install-uv" | "create-venv" | "install-openfic" | "start-backend" | "health-check";
  status: "running" | "done" | "failed";
  message: string;
}

export interface SaveConfigRequest {
  config: DesktopConfig;
}

export interface CheckRemoteRequest {
  url: string;
}

export interface InitializeAppResult {
  status: "ready" | "needs-setup";
  message?: string;
}
