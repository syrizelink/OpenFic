export type DesktopInstanceMode = "local" | "remote";

export interface DesktopInstance {
  id: string;
  name: string;
  mode: DesktopInstanceMode;
  remoteUrl: string | null;
  autoStartLocal: boolean;
  installDir: string | null;
  /** Works data directory. `null` means the default (current) location. */
  dataDir: string | null;
  favorite?: boolean;
}

export interface DesktopConfig {
  activeInstanceId: string | null;
  instances: DesktopInstance[];
  zoomFactor?: number;
}

export interface RuntimeConfigResponse {
  backendBaseUrl: string;
}

export const defaultDesktopConfig: DesktopConfig = {
  activeInstanceId: null,
  instances: [],
};
