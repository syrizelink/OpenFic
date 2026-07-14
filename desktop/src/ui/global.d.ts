import type { DesktopConfig } from "../shared/config";
import type {
  CheckDirectoryEmptyResult,
  InitializeAppResult,
  PingInstanceResult,
  SetupProgressEvent,
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
      checkDirectoryEmpty: (dirPath: string) => Promise<CheckDirectoryEmptyResult>;
      closeSetup: () => Promise<void>;
      showSetup: () => Promise<void>;
      frontendHostPreloadPath: string;
      minimizeWindow: () => Promise<void>;
      toggleMaximizeWindow: () => Promise<void>;
      closeWindow: () => Promise<void>;
      getUpdateState: () => Promise<UpdateState>;
      checkForUpdate: () => Promise<void>;
      downloadUpdate: () => Promise<void>;
      installUpdate: () => Promise<void>;
      onSetupProgress: (handler: (event: SetupProgressEvent) => void) => () => void;
      onUpdateState: (handler: (state: UpdateState) => void) => () => void;
    };
  }
}
