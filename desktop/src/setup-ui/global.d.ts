import type { DesktopConfig } from "../shared/config";
import type { InitializeAppResult, SetupProgressEvent } from "../shared/ipc";

declare global {
  interface Window {
    openficDesktop: {
      getConfig: () => Promise<DesktopConfig | null>;
      saveConfig: (config: DesktopConfig) => Promise<void>;
      initializeApp: () => Promise<InitializeAppResult>;
      runLocalSetup: () => Promise<void>;
      checkRemote: (url: string) => Promise<void>;
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
