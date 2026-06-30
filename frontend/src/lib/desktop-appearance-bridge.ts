import type { ThemeMode } from "@/features/settings/lib/settings.types";

export interface DesktopAppearancePayload {
  appearance?: ThemeMode;
  fontFamily?: string;
  codeFontFamily?: string;
}

declare global {
  interface Window {
    openficDesktopHost?: {
      publishAppearance: (payload: DesktopAppearancePayload) => void;
    };
  }
}

export function publishDesktopAppearance(payload: DesktopAppearancePayload): void {
  window.openficDesktopHost?.publishAppearance(payload);
}
