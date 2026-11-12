import type { LanguageCode } from "@/i18n";
import type { ThemeAppearance, ThemeVariables } from "@/lib/theme";

export interface DesktopAppearancePayload {
  appearance?: ThemeAppearance;
  fontFamily?: string;
  codeFontFamily?: string;
  themeVariables?: ThemeVariables;
  persist?: boolean;
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
      openExternalLink: (url: string) => Promise<void>;
      publishAppearance: (payload: DesktopAppearancePayload) => void;
      publishLanguage: (language: LanguageCode) => void;
      publishSocketDiagnostic: (payload: SocketDiagnosticPayload) => void;
      openOpenAICodexAuthorization: (url: string) => Promise<void>;
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

export function openExternalLink(url: string): void {
  const desktopHost = window.openficDesktopHost;
  if (desktopHost) {
    void desktopHost.openExternalLink(url).catch((error: unknown) => {
      console.error(
        `Failed to open external link: ${error instanceof Error ? error.message : String(error)}`,
      );
    });
    return;
  }

  window.open(url, "_blank", "noopener,noreferrer");
}
