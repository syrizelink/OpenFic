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
  inspectLocalRuntime: "setup:inspect-local-runtime",
  setupProgress: "setup:progress",
  getStartupProgress: "app:get-startup-progress",
  startupProgress: "app:startup-progress",
  closeSetup: "setup:close",
  showSetup: "shell:show-setup",
  minimizeWindow: "window:minimize",
  toggleMaximizeWindow: "window:toggle-maximize",
  closeWindow: "window:close",
  getUpdateState: "update:get-state",
  checkForUpdate: "update:check",
  downloadUpdate: "update:download",
  cancelUpdateDownload: "update:cancel-download",
  installUpdate: "update:install",
  openUpdateRelease: "update:open-release",
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

export interface InspectLocalRuntimeRequest {
  installDir: string;
}

export interface InspectLocalRuntimeResult {
  status: "missing" | "incomplete" | "ready";
  message: string;
  configuredInstance: DesktopInstance | null;
}

export interface InitializeAppResult {
  status: "ready" | "needs-setup";
  activeInstanceId?: string | null;
  message?: string;
  compatibilityWarning?: string;
}

export type StartupStep =
  | "load-config"
  | "check-runtime"
  | "update-python"
  | "update-openfic"
  | "start-backend"
  | "initialize-backend"
  | "initialize-database"
  | "complete-backend-startup"
  | "check-health"
  | "connect-remote"
  | "verify-remote"
  | "check-compatibility"
  | "ready";

export interface StartupProgressEvent {
  step: StartupStep;
  status: "running" | "done" | "failed";
  title: string;
  message: string;
  /** Overall startup progress as a 0..1 fraction. */
  progress: number;
}

export type UpdateStatus = "unsupported" | "idle" | "checking" | "available" | "downloading" | "downloaded" | "not-available" | "error";

export interface UpdateState {
  status: UpdateStatus;
  version?: string;
  releaseNotes?: string;
  progress?: number;
  transferred?: number;
  total?: number;
  bytesPerSecond?: number;
  message?: string;
}
