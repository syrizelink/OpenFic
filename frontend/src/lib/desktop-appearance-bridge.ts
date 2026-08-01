import type { ThemeMode } from "@/features/settings/lib/settings.types";
import type { LanguageCode } from "@/i18n";

export interface DesktopAppearancePayload {
  appearance?: ThemeMode;
  fontFamily?: string;
  codeFontFamily?: string;
}

declare global {
  interface Window {
    openficDesktopHost?: {
      publishAppearance: (payload: DesktopAppearancePayload) => void;
      publishLanguage: (language: LanguageCode) => void;
    };
  }
}

export function publishDesktopAppearance(payload: DesktopAppearancePayload): void {
  window.openficDesktopHost?.publishAppearance?.(payload);
}

export function publishDesktopLanguage(language: LanguageCode): void {
  window.openficDesktopHost?.publishLanguage?.(language);
}
