import type { DesktopConfig, DesktopInstance } from "./config.js";

export const IpcChannels = {
  getConfig: "config:get",
  saveConfig: "config:save",
  initializeApp: "app:initialize",
  ensureInstanceSession: "app:ensure-instance-session",
  getDefaultInstallDir: "app:default-install-dir",
  installRuntime: "setup:install-runtime",
  startLocalBackend: "setup:start-local-backend",
  checkRemote: "setup:check-remote",
  switchInstance: "instance:switch",
  pingInstance: "instance:ping",
  selectDirectory: "dialog:select-directory",
  checkDirectoryEmpty: "directory:check-empty",
  setupProgress: "setup:progress",
  closeSetup: "setup:close",
  showSetup: "shell:show-setup",
  minimizeWindow: "window:minimize",
  toggleMaximizeWindow: "window:toggle-maximize",
  closeWindow: "window:close",
  getUpdateState: "update:get-state",
  checkForUpdate: "update:check",
  downloadUpdate: "update:download",
  installUpdate: "update:install",
  updateState: "update:state",
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

export interface EnsureInstanceSessionRequest {
  partition: string;
}

export interface SwitchInstanceRequest {
  instanceId: string;
}

export interface PingInstanceRequest {
  instance: DesktopInstance;
}

export interface PingInstanceResult {
  latencyMs: number;
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
  activeInstanceId?: string | null;
  message?: string;
  compatibilityWarning?: string;
}

export type UpdateStatus = "unsupported" | "idle" | "checking" | "available" | "downloading" | "downloaded" | "not-available" | "error";

export interface UpdateState {
  status: UpdateStatus;
  version?: string;
  progress?: number;
  transferred?: number;
  total?: number;
  message?: string;
}
