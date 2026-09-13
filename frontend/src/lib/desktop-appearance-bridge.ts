import type { LanguageCode } from "@/i18n";
import type { ThemeAppearance } from "@/lib/theme";

export interface DesktopAppearancePayload {
  appearance?: ThemeAppearance;
  fontFamily?: string;
  codeFontFamily?: string;
}

export interface SocketDiagnosticPayload {
  event:
    | "connect-start"
    | "connect-error"
    | "reconnect-attempt"
    | "reconnect-failed"
    | "connected"
    | "disconnected"
    | "connection-timeout";
  active?: boolean;
  attempt?: number;
  durationMs?: number;
  message?: string;
  transport?: string;
  url?: string;
}

declare global {
  interface Window {
    openficDesktopHost?: {
      publishAppearance: (payload: DesktopAppearancePayload) => void;
      publishLanguage: (language: LanguageCode) => void;
      publishSocketDiagnostic: (payload: SocketDiagnosticPayload) => void;
    };
  }
}

export function publishDesktopAppearance(payload: DesktopAppearancePayload): void {
  window.openficDesktopHost?.publishAppearance(payload);
}

export function publishDesktopLanguage(language: LanguageCode): void {
  window.openficDesktopHost?.publishLanguage(language);
}

export function publishSocketDiagnostic(payload: SocketDiagnosticPayload): void {
  window.openficDesktopHost?.publishSocketDiagnostic?.(payload);
}
