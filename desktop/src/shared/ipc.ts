import type { DesktopConfig, DesktopInstance } from "./config.js";

export const IpcChannels = {
  getConfig: "config:get",
  saveConfig: "config:save",
  initializeApp: "app:initialize",
  cancelStartup: "app:cancel-startup",
  ensureInstanceSession: "app:ensure-instance-session",
  getDefaultInstallDir: "app:default-install-dir",
  installRuntime: "setup:install-runtime",
  startLocalBackend: "setup:start-local-backend",
  switchInstance: "instance:switch",
  getInstanceDeletionInfo: "instance:get-deletion-info",
  deleteInstance: "instance:delete",
  pingInstance: "instance:ping",
  selectDirectory: "dialog:select-directory",
  inspectLocalRuntime: "setup:inspect-local-runtime",
  setupProgress: "setup:progress",
  getStartupProgress: "app:get-startup-progress",
  startupProgress: "app:startup-progress",
  minimizeWindow: "window:minimize",
  toggleMaximizeWindow: "window:toggle-maximize",
  toggleFullScreen: "window:toggle-full-screen",
  reloadWindow: "window:reload",
  toggleDevTools: "window:toggle-dev-tools",
  closeWindow: "window:close",
  getUpdateState: "update:get-state",
  checkForUpdate: "update:check",
  downloadUpdate: "update:download",
  cancelUpdateDownload: "update:cancel-download",
  installUpdate: "update:install",
  openUpdateRelease: "update:open-release",
  updateState: "update:state",
  exportLogs: "logs:export",
  logFrontendDiagnostic: "logs:frontend-diagnostic",
  reportError: "telemetry:report-error",
  openProjectHome: "help:open-project-home",
  reportBug: "help:report-bug",
  suggestFeature: "help:suggest-feature",
  getZoomFactor: "zoom:get-factor",
  saveZoomFactor: "zoom:save-factor",
  zoomFactorChanged: "zoom:changed",
  getDefaultDataDir: "data:get-default-dir",
  getDataInfo: "data:get-info",
  inspectDataDir: "data:inspect-dir",
  migrateData: "data:migrate",
  backupData: "data:backup",
  restoreData: "data:restore",
  dataProgress: "data:progress",
  selectSaveFile: "dialog:select-save-file",
  selectOpenFile: "dialog:select-open-file",
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

export interface SaveZoomFactorRequest {
  zoomFactor: number;
}

export interface LogFrontendDiagnosticRequest {
  message: string;
}

export interface ReportErrorPayload {
  name: string;
  message: string;
  stack?: string;
}

export interface EnsureInstanceSessionRequest {
  partition: string;
}

export interface SwitchInstanceRequest {
  instanceId: string;
}

export interface GetInstanceDeletionInfoRequest {
  instanceId: string;
}

export interface InstanceDeletionInfo {
  dataDir: string | null;
  dataDirShared: boolean;
  runtimeDir: string | null;
  runtimeDirShared: boolean;
}

export interface DeleteInstanceRequest {
  instanceId: string;
  deleteData: boolean;
}

export interface DeleteInstanceResult {
  nextActiveInstanceId: string | null;
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
  dataDir?: string | null;
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
  maintenanceWarning?: string;
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
  | "maintain-database"
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
  /** Whether the current operation has no reliable percentage. */
  indeterminate?: boolean;
  /** Backend maintenance phase used to localize the current detail. */
  maintenancePhase?:
    | "pending"
    | "pruning"
    | "migrating"
    | "vacuuming"
    | "cleanup"
    | "ready"
    | "failed";
  /** Backend maintenance internal progress (0..1), shown as text detail. */
  maintenanceProgress?: number | null;
  /** Backend maintenance reclaimed bytes (current), shown as text detail. */
  maintenanceReclaimedBytes?: number | null;
  /** Backend maintenance estimated total bytes, shown as text detail. */
  maintenanceTotalBytes?: number | null;
  /** Backend maintenance VACUUM VM operations, shown as text detail. */
  maintenanceVmOps?: number | null;
  /** Backend maintenance elapsed seconds, shown as text detail. */
  maintenanceElapsedSeconds?: number | null;
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

export interface DataInfo {
  /** Resolved absolute path of the instance data directory. */
  dataDir: string;
  /** Whether the instance falls back to the default data location. */
  isDefaultLocation: boolean;
  hasData: boolean;
  entryCount: number;
  sizeBytes: number;
}

export interface InspectDataDirResult {
  /** Whether the directory contains recognizable OpenFic data. */
  valid: boolean;
  hasData: boolean;
  entryCount: number;
  sizeBytes: number;
}

export interface GetDataInfoRequest {
  instanceId: string;
}

export interface InspectDataDirRequest {
  dataDir: string;
}

export interface MigrateDataRequest {
  instanceId: string;
  newDataDir: string;
  deleteOldDir: boolean;
}

export interface MigrateDataResult {
  dataDir: string;
  migrated: boolean;
  removedOldDir: boolean;
}

export interface BackupDataRequest {
  instanceId: string;
  targetPath: string;
}

export interface RestoreDataRequest {
  instanceId: string;
  sourcePath: string;
}

export type DataOperationPhase = "extract" | "verify" | "rollback" | "copy" | "cleanup" | "pack" | "delete-old";

export interface DataProgressEvent {
  operation: "backup" | "restore" | "migrate";
  phase: DataOperationPhase;
  /** Overall progress of the current phase as a 0..1 fraction when available. */
  progress?: number;
}
