import type { DesktopConfig } from "./config.js";

export const IpcChannels = {
  getConfig: "config:get",
  saveConfig: "config:save",
  initializeApp: "app:initialize",
  getDefaultInstallDir: "app:default-install-dir",
  installRuntime: "setup:install-runtime",
  startLocalBackend: "setup:start-local-backend",
  checkRemote: "setup:check-remote",
  selectDirectory: "dialog:select-directory",
  checkDirectoryEmpty: "directory:check-empty",
  setupProgress: "setup:progress",
  closeSetup: "setup:close",
  showSetup: "shell:show-setup",
  minimizeWindow: "window:minimize",
  toggleMaximizeWindow: "window:toggle-maximize",
  closeWindow: "window:close",
} as const;

export type SetupStep =
  | "download-python"
  | "extract-python"
  | "create-venv"
  | "install-uv"
  | "install-openfic";

export interface SetupProgressEvent {
  step: SetupStep;
  status: "running" | "done" | "failed";
  message: string;
  /** Download/extraction progress as a 0..1 fraction when available. */
  progress?: number;
}

export interface SaveConfigRequest {
  config: DesktopConfig;
}

export interface CheckRemoteRequest {
  url: string;
}

export interface InstallRuntimeRequest {
  installDir: string;
}

export interface StartLocalBackendRequest {
  installDir: string;
}

export interface CheckDirectoryEmptyRequest {
  path: string;
}

export interface CheckDirectoryEmptyResult {
  exists: boolean;
  empty: boolean;
}

export interface InitializeAppResult {
  status: "ready" | "needs-setup";
  message?: string;
}
