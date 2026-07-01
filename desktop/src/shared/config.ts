export type DesktopInstanceMode = "local" | "remote";

export interface DesktopInstance {
  id: string;
  name: string;
  mode: DesktopInstanceMode;
  remoteUrl: string | null;
  autoStartLocal: boolean;
  installDir: string | null;
  favorite?: boolean;
}

export interface DesktopConfig {
  activeInstanceId: string | null;
  instances: DesktopInstance[];
}

export interface RuntimeConfigResponse {
  backendBaseUrl: string;
}

export const defaultDesktopConfig: DesktopConfig = {
  activeInstanceId: null,
  instances: [],
};
