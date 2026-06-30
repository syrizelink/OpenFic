import type { DesktopConfig } from "../shared/config";
import type { SetupProgressEvent } from "../shared/ipc";

declare global {
  interface Window {
    openficDesktop: {
      getConfig: () => Promise<DesktopConfig | null>;
      saveConfig: (config: DesktopConfig) => Promise<void>;
      runLocalSetup: () => Promise<void>;
      checkRemote: (url: string) => Promise<void>;
      closeSetup: () => Promise<void>;
      onSetupProgress: (handler: (event: SetupProgressEvent) => void) => () => void;
    };
  }
}
