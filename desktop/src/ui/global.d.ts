import type { DesktopConfig } from "../shared/config";
import type {
  CheckDirectoryEmptyResult,
  InitializeAppResult,
  SetupProgressEvent,
} from "../shared/ipc";

declare global {
  interface Window {
    openficDesktop: {
      getConfig: () => Promise<DesktopConfig | null>;
      saveConfig: (config: DesktopConfig) => Promise<void>;
      initializeApp: () => Promise<InitializeAppResult>;
      getDefaultInstallDir: () => Promise<string>;
      installRuntime: (installDir: string) => Promise<void>;
      startLocalBackend: (installDir: string) => Promise<void>;
      checkRemote: (url: string) => Promise<void>;
      selectDirectory: () => Promise<string | null>;
      checkDirectoryEmpty: (dirPath: string) => Promise<CheckDirectoryEmptyResult>;
      closeSetup: () => Promise<void>;
      showSetup: () => Promise<void>;
      frontendHostPreloadPath: string;
      minimizeWindow: () => Promise<void>;
      toggleMaximizeWindow: () => Promise<void>;
      closeWindow: () => Promise<void>;
      onSetupProgress: (handler: (event: SetupProgressEvent) => void) => () => void;
    };
  }
}
