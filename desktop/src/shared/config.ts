export interface DesktopConfig {
  mode: "local" | "remote";
  remoteUrl: string | null;
  autoStartLocal: boolean;
}

export interface RuntimeConfigResponse {
  backendBaseUrl: string;
}

export const defaultDesktopConfig: DesktopConfig = {
  mode: "local",
  remoteUrl: null,
  autoStartLocal: true,
};
