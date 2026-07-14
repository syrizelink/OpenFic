import type { DesktopConfig } from "../shared/config";
import type {
  InspectLocalRuntimeResult,
  InitializeAppResult,
  PingInstanceResult,
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
      ensureInstanceSession: (partition: string) => Promise<void>;
      getDefaultInstallDir: () => Promise<string>;
      installRuntime: (installDir: string) => Promise<void>;
      startLocalBackend: (installDir: string) => Promise<void>;
      checkRemote: (url: string) => Promise<void>;
      switchInstance: (instanceId: string) => Promise<InitializeAppResult>;
      pingInstance: (instance: DesktopInstance) => Promise<PingInstanceResult>;
      selectDirectory: () => Promise<string | null>;
      inspectLocalRuntime: (installDir: string) => Promise<InspectLocalRuntimeResult>;
      closeSetup: () => Promise<void>;
      showSetup: () => Promise<void>;
      frontendHostPreloadPath: string;
      minimizeWindow: () => Promise<void>;
      toggleMaximizeWindow: () => Promise<void>;
      closeWindow: () => Promise<void>;
      getUpdateState: () => Promise<UpdateState>;
      getStartupProgress: () => Promise<StartupProgressEvent | null>;
      checkForUpdate: () => Promise<void>;
      downloadUpdate: () => Promise<void>;
      cancelUpdateDownload: () => Promise<void>;
      installUpdate: () => Promise<void>;
      openUpdateRelease: () => Promise<void>;
      onSetupProgress: (handler: (event: SetupProgressEvent) => void) => () => void;
      onStartupProgress: (handler: (event: StartupProgressEvent) => void) => () => void;
      onUpdateState: (handler: (state: UpdateState) => void) => () => void;
    };
  }
}
