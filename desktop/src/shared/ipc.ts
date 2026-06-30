import type { DesktopConfig } from "./config.js";

export const IpcChannels = {
  getConfig: "config:get",
  saveConfig: "config:save",
  runLocalSetup: "setup:run-local",
  checkRemote: "setup:check-remote",
  setupProgress: "setup:progress",
  closeSetup: "setup:close",
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
