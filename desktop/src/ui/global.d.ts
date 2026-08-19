import type { DesktopConfig } from "../shared/config";
import type {
  DataInfo,
  DataProgressEvent,
  DeleteInstanceResult,
  InspectDataDirResult,
  InstanceDeletionInfo,
  InspectLocalRuntimeResult,
  InitializeAppResult,
  MigrateDataResult,
  PingInstanceResult,
  ReportErrorPayload,
  SetupProgressEvent,
  StartupProgressEvent,
  UpdateState,
} from "../shared/ipc";
import type { DesktopInstance } from "../shared/config";

declare global {
  interface Window {
    openficDesktop: {
      getConfig: () => Promise<DesktopConfig | null>;
      saveConfig: (config: DesktopConfig) => Promise<void>;
      initializeApp: () => Promise<InitializeAppResult>;
      cancelStartup: () => Promise<void>;
      ensureInstanceSession: (partition: string) => Promise<void>;
      getDefaultInstallDir: () => Promise<string>;
      installRuntime: (installDir: string) => Promise<void>;
      startLocalBackend: (installDir: string, dataDir?: string | null) => Promise<string | null>;
      switchInstance: (instanceId: string) => Promise<InitializeAppResult>;
      getInstanceDeletionInfo: (instanceId: string) => Promise<InstanceDeletionInfo>;
      deleteInstance: (instanceId: string, deleteData: boolean) => Promise<DeleteInstanceResult>;
      pingInstance: (instance: DesktopInstance) => Promise<PingInstanceResult>;
      selectDirectory: () => Promise<string | null>;
      selectSaveFile: () => Promise<string | null>;
      selectOpenFile: () => Promise<string | null>;
      getDefaultDataDir: () => Promise<string>;
      getDataInfo: (instanceId: string) => Promise<DataInfo>;
      inspectDataDir: (dataDir: string) => Promise<InspectDataDirResult>;
      migrateData: (instanceId: string, newDataDir: string, deleteOldDir: boolean) => Promise<MigrateDataResult>;
      backupData: (instanceId: string, targetPath: string) => Promise<void>;
      restoreData: (instanceId: string, sourcePath: string) => Promise<void>;
      inspectLocalRuntime: (installDir: string) => Promise<InspectLocalRuntimeResult>;
      frontendHostPreloadPath: string;
      minimizeWindow: () => Promise<void>;
      toggleMaximizeWindow: () => Promise<void>;
      toggleFullScreen: () => Promise<void>;
      reloadWindow: () => Promise<void>;
      toggleDevTools: () => Promise<void>;
      closeWindow: () => Promise<void>;
      getUpdateState: () => Promise<UpdateState>;
      getStartupProgress: () => Promise<StartupProgressEvent | null>;
      checkForUpdate: () => Promise<void>;
      downloadUpdate: () => Promise<void>;
      cancelUpdateDownload: () => Promise<void>;
      installUpdate: () => Promise<void>;
      openUpdateRelease: () => Promise<void>;
      exportLogs: () => Promise<string | null>;
      logFrontendDiagnostic: (message: string) => Promise<void>;
      reportError: (payload: ReportErrorPayload) => void;
      openProjectHome: () => Promise<void>;
      reportBug: () => Promise<void>;
      suggestFeature: () => Promise<void>;
      getZoomFactor: () => Promise<number>;
      saveZoomFactor: (zoomFactor: number) => Promise<void>;
      onZoomFactorChanged: (handler: (zoomFactor: number) => void) => () => void;
      onSetupProgress: (handler: (event: SetupProgressEvent) => void) => () => void;
      onDataProgress: (handler: (event: DataProgressEvent) => void) => () => void;
      onStartupProgress: (handler: (event: StartupProgressEvent) => void) => () => void;
      onUpdateState: (handler: (state: UpdateState) => void) => () => void;
    };
  }
}
