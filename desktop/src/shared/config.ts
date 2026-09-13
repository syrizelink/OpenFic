export type DesktopInstanceMode = "local" | "remote";
export type DesktopAppearance = "light" | "dark";

export interface DesktopInstanceAppearance {
  appearance?: DesktopAppearance;
  fontFamily?: string;
  codeFontFamily?: string;
  themeVariables?: Record<string, string>;
}

const THEME_VARIABLE_NAME_PATTERN = /^--(?:accent|gray|theme|color)-[a-z0-9-]+$/;
const MAX_THEME_VARIABLE_COUNT = 128;
const MAX_THEME_VARIABLE_VALUE_LENGTH = 256;

export function isDesktopThemeVariables(value: unknown): value is Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const entries = Object.entries(value);
  return (
    entries.length > 0 &&
    entries.length <= MAX_THEME_VARIABLE_COUNT &&
    entries.every(
      ([name, variableValue]) =>
        THEME_VARIABLE_NAME_PATTERN.test(name) &&
        typeof variableValue === "string" &&
        variableValue.length > 0 &&
        variableValue.length <= MAX_THEME_VARIABLE_VALUE_LENGTH,
    )
  );
}

export function isDesktopInstanceAppearance(value: unknown): value is DesktopInstanceAppearance {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as DesktopInstanceAppearance;
  return (
    (candidate.appearance === undefined || candidate.appearance === "light" || candidate.appearance === "dark") &&
    (candidate.fontFamily === undefined || typeof candidate.fontFamily === "string") &&
    (candidate.codeFontFamily === undefined || typeof candidate.codeFontFamily === "string") &&
    (candidate.themeVariables === undefined || isDesktopThemeVariables(candidate.themeVariables))
  );
}

export interface DesktopInstance extends DesktopInstanceAppearance {
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
