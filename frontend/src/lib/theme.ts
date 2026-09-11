export interface ThemePalette {
  background: string;
  sidebarBackground: string;
  panelBackground: string;
  editorBackground: string;
  inputBackground: string;
  foreground: string;
  mutedForeground: string;
  border: string;
  borderSubtle: string;
  hoverBackground: string;
  selectionBackground: string;
  selectionForeground: string;
  accent: string;
  accentForeground: string;
  accentHover: string;
  link: string;
}

export interface ThemeConfig {
  light: ThemePalette;
  dark: ThemePalette;
}

export interface ThemePaletteResponse {
  background?: string;
  sidebar_background?: string;
  panel_background?: string;
  editor_background?: string;
  input_background?: string;
  foreground?: string;
  muted_foreground?: string;
  border?: string;
  border_subtle?: string;
  hover_background?: string;
  selection_background?: string;
  selection_foreground?: string;
  accent?: string;
  accent_foreground?: string;
  accent_hover?: string;
  link?: string;
}

export interface ThemeConfigResponse {
  light?: ThemePaletteResponse;
  dark?: ThemePaletteResponse;
}

export interface ThemeSettings {
  theme: ThemeAppearance;
  themePreset: ThemePresetId;
  lightThemePreset: ThemePresetId;
  darkThemePreset: ThemePresetId;
  themeConfig: ThemeConfig;
}

export interface ThemePreset {
  id: string;
  labelKey: string;
  defaultAppearance: ThemeAppearance;
  light: ThemePalette;
  dark: ThemePalette;
}

export const DEFAULT_THEME_PRESET_ID = "classic" as const;
export const CUSTOM_THEME_PRESET_ID = "custom" as const;

const CLASSIC_LIGHT_PALETTE: ThemePalette = {
  background: "#ffffff",
  sidebarBackground: "#ffffff",
  panelBackground: "#ffffff",
  editorBackground: "#ffffff",
  inputBackground: "#ffffff",
  foreground: "#202020",
  mutedForeground: "#646464",
  border: "#d9d9d9",
  borderSubtle: "#e8e8e8",
  hoverBackground: "#f0f0f0",
  selectionBackground: "#e5e5e5",
  selectionForeground: "#202020",
  accent: "#000000",
  accentForeground: "#ffffff",
  accentHover: "#1a1a1a",
  link: "#0969da",
};

const CLASSIC_DARK_PALETTE: ThemePalette = {
  background: "#111111",
  sidebarBackground: "#111111",
  panelBackground: "#191919",
  editorBackground: "#111111",
  inputBackground: "#191919",
  foreground: "#eeeeee",
  mutedForeground: "#b4b4b4",
  border: "#3a3a3a",
  borderSubtle: "#2a2a2a",
  hoverBackground: "#222222",
  selectionBackground: "#262626",
  selectionForeground: "#eeeeee",
  accent: "#ffffff",
  accentForeground: "#000000",
  accentHover: "#f5f5f5",
  link: "#0969da",
};

const VSCODE_DARK_PALETTE: ThemePalette = {
  background: "#1e1e1e",
  sidebarBackground: "#181818",
  panelBackground: "#252526",
  editorBackground: "#1e1e1e",
  inputBackground: "#3c3c3c",
  foreground: "#d4d4d4",
  mutedForeground: "#9d9d9d",
  border: "#3e3e42",
  borderSubtle: "#2d2d2d",
  hoverBackground: "#2a2d2e",
  selectionBackground: "#264f78",
  selectionForeground: "#ffffff",
  accent: "#007acc",
  accentForeground: "#ffffff",
  accentHover: "#1f8ad2",
  link: "#3794ff",
};

const SOLARIZED_LIGHT_PALETTE: ThemePalette = {
  background: "#fdf6e3",
  sidebarBackground: "#eee8d5",
  panelBackground: "#fdf6e3",
  editorBackground: "#fdf6e3",
  inputBackground: "#eee8d5",
  foreground: "#657b83",
  mutedForeground: "#839496",
  border: "#d6cdb0",
  borderSubtle: "#eee8d5",
  hoverBackground: "#eee8d5",
  selectionBackground: "#b3d4cf",
  selectionForeground: "#073642",
  accent: "#268bd2",
  accentForeground: "#fdf6e3",
  accentHover: "#2aa198",
  link: "#2aa198",
};

const SOLARIZED_DARK_PALETTE: ThemePalette = {
  background: "#002b36",
  sidebarBackground: "#073642",
  panelBackground: "#073642",
  editorBackground: "#002b36",
  inputBackground: "#073642",
  foreground: "#839496",
  mutedForeground: "#657b83",
  border: "#586e75",
  borderSubtle: "#073642",
  hoverBackground: "#0b3b46",
  selectionBackground: "#0b4f5a",
  selectionForeground: "#93a1a1",
  accent: "#268bd2",
  accentForeground: "#fdf6e3",
  accentHover: "#2aa198",
  link: "#2aa198",
};

const NORD_LIGHT_PALETTE: ThemePalette = {
  background: "#eceff4",
  sidebarBackground: "#e5e9f0",
  panelBackground: "#f5f7fa",
  editorBackground: "#eceff4",
  inputBackground: "#e5e9f0",
  foreground: "#2e3440",
  mutedForeground: "#5e6675",
  border: "#c8d0dc",
  borderSubtle: "#d8dee9",
  hoverBackground: "#e5e9f0",
  selectionBackground: "#cbd5e1",
  selectionForeground: "#2e3440",
  accent: "#5e81ac",
  accentForeground: "#ffffff",
  accentHover: "#4c6d95",
  link: "#5e81ac",
};

const NORD_DARK_PALETTE: ThemePalette = {
  background: "#2e3440",
  sidebarBackground: "#242933",
  panelBackground: "#3b4252",
  editorBackground: "#2e3440",
  inputBackground: "#434c5e",
  foreground: "#d8dee9",
  mutedForeground: "#9aa5b5",
  border: "#4c566a",
  borderSubtle: "#3b4252",
  hoverBackground: "#434c5e",
  selectionBackground: "#4c566a",
  selectionForeground: "#eceff4",
  accent: "#88c0d0",
  accentForeground: "#2e3440",
  accentHover: "#8fbcbb",
  link: "#81a1c1",
};

const MONOKAI_LIGHT_PALETTE: ThemePalette = {
  background: "#faf8f2",
  sidebarBackground: "#f1eee5",
  panelBackground: "#ffffff",
  editorBackground: "#faf8f2",
  inputBackground: "#f1eee5",
  foreground: "#272822",
  mutedForeground: "#75715e",
  border: "#d8d5ca",
  borderSubtle: "#e9e6dc",
  hoverBackground: "#ece9df",
  selectionBackground: "#c8c8c8",
  selectionForeground: "#272822",
  accent: "#66a80f",
  accentForeground: "#ffffff",
  accentHover: "#4f8308",
  link: "#1e7f78",
};

const MONOKAI_DARK_PALETTE: ThemePalette = {
  background: "#272822",
  sidebarBackground: "#1f201b",
  panelBackground: "#3e3d32",
  editorBackground: "#272822",
  inputBackground: "#3e3d32",
  foreground: "#f8f8f2",
  mutedForeground: "#a6a6a0",
  border: "#49483e",
  borderSubtle: "#3b3a32",
  hoverBackground: "#3e3d32",
  selectionBackground: "#49483e",
  selectionForeground: "#f8f8f2",
  accent: "#a6e22e",
  accentForeground: "#272822",
  accentHover: "#c1f85a",
  link: "#66d9ef",
};

export const DEFAULT_THEME_CONFIG: ThemeConfig = {
  light: CLASSIC_LIGHT_PALETTE,
  dark: CLASSIC_DARK_PALETTE,
};

export const THEME_PRESETS = [
  {
    id: DEFAULT_THEME_PRESET_ID,
    labelKey: "settings.themePresetClassic",
    defaultAppearance: "light",
    light: CLASSIC_LIGHT_PALETTE,
    dark: CLASSIC_DARK_PALETTE,
  },
  {
    id: "vscode-dark",
    labelKey: "settings.themePresetVSCode",
    defaultAppearance: "dark",
    light: CLASSIC_LIGHT_PALETTE,
    dark: VSCODE_DARK_PALETTE,
  },
  {
    id: "solarized",
    labelKey: "settings.themePresetSolarized",
    defaultAppearance: "light",
    light: SOLARIZED_LIGHT_PALETTE,
    dark: SOLARIZED_DARK_PALETTE,
  },
  {
    id: "nord",
    labelKey: "settings.themePresetNord",
    defaultAppearance: "dark",
    light: NORD_LIGHT_PALETTE,
    dark: NORD_DARK_PALETTE,
  },
  {
    id: "monokai",
    labelKey: "settings.themePresetMonokai",
    defaultAppearance: "dark",
    light: MONOKAI_LIGHT_PALETTE,
    dark: MONOKAI_DARK_PALETTE,
  },
] as const satisfies readonly ThemePreset[];

export const CUSTOM_THEME_PRESET = {
  id: CUSTOM_THEME_PRESET_ID,
  labelKey: "settings.themePresetCustom",
  defaultAppearance: "light",
  light: CLASSIC_LIGHT_PALETTE,
  dark: CLASSIC_DARK_PALETTE,
} as const satisfies ThemePreset;

export type ThemePresetId = (typeof THEME_PRESETS)[number]["id"] | typeof CUSTOM_THEME_PRESET_ID;
export type ThemeAppearance = "light" | "dark";

export const THEME_PALETTE_FIELDS = [
  { key: "background", labelKey: "settings.themeColorBackground" },
  { key: "sidebarBackground", labelKey: "settings.themeColorSidebarBackground" },
  { key: "panelBackground", labelKey: "settings.themeColorPanelBackground" },
  { key: "editorBackground", labelKey: "settings.themeColorEditorBackground" },
  { key: "inputBackground", labelKey: "settings.themeColorInputBackground" },
  { key: "foreground", labelKey: "settings.themeColorForeground" },
  { key: "mutedForeground", labelKey: "settings.themeColorMutedForeground" },
  { key: "border", labelKey: "settings.themeColorBorder" },
  { key: "borderSubtle", labelKey: "settings.themeColorBorderSubtle" },
  { key: "hoverBackground", labelKey: "settings.themeColorHoverBackground" },
  { key: "selectionBackground", labelKey: "settings.themeColorSelectionBackground" },
  { key: "selectionForeground", labelKey: "settings.themeColorSelectionForeground" },
  { key: "accent", labelKey: "settings.themeColorAccent" },
  { key: "accentForeground", labelKey: "settings.themeColorAccentForeground" },
  { key: "accentHover", labelKey: "settings.themeColorAccentHover" },
  { key: "link", labelKey: "settings.themeColorLink" },
] as const;

type ThemePaletteInput = Partial<Record<keyof ThemePalette, unknown>>;

function isHexColor(value: unknown): value is string {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}

function normalizeColor(value: unknown, fallback: string): string {
  return isHexColor(value) ? value : fallback;
}

export function normalizeThemePalette(
  palette: ThemePaletteInput | null | undefined,
  fallback: ThemePalette = CLASSIC_LIGHT_PALETTE,
): ThemePalette {
  return {
    background: normalizeColor(palette?.background, fallback.background),
    sidebarBackground: normalizeColor(palette?.sidebarBackground, fallback.sidebarBackground),
    panelBackground: normalizeColor(palette?.panelBackground, fallback.panelBackground),
    editorBackground: normalizeColor(palette?.editorBackground, fallback.editorBackground),
    inputBackground: normalizeColor(palette?.inputBackground, fallback.inputBackground),
    foreground: normalizeColor(palette?.foreground, fallback.foreground),
    mutedForeground: normalizeColor(palette?.mutedForeground, fallback.mutedForeground),
    border: normalizeColor(palette?.border, fallback.border),
    borderSubtle: normalizeColor(palette?.borderSubtle, fallback.borderSubtle),
    hoverBackground: normalizeColor(palette?.hoverBackground, fallback.hoverBackground),
    selectionBackground: normalizeColor(palette?.selectionBackground, fallback.selectionBackground),
    selectionForeground: normalizeColor(palette?.selectionForeground, fallback.selectionForeground),
    accent: normalizeColor(palette?.accent, fallback.accent),
    accentForeground: normalizeColor(palette?.accentForeground, fallback.accentForeground),
    accentHover: normalizeColor(palette?.accentHover, fallback.accentHover),
    link: normalizeColor(palette?.link, fallback.link),
  };
}

function transformThemePalette(
  palette: ThemePaletteResponse | null | undefined,
  fallback: ThemePalette,
): ThemePalette {
  return normalizeThemePalette(
    {
      background: palette?.background,
      sidebarBackground: palette?.sidebar_background,
      panelBackground: palette?.panel_background,
      editorBackground: palette?.editor_background,
      inputBackground: palette?.input_background,
      foreground: palette?.foreground,
      mutedForeground: palette?.muted_foreground,
      border: palette?.border,
      borderSubtle: palette?.border_subtle,
      hoverBackground: palette?.hover_background,
      selectionBackground: palette?.selection_background,
      selectionForeground: palette?.selection_foreground,
      accent: palette?.accent,
      accentForeground: palette?.accent_foreground,
      accentHover: palette?.accent_hover,
      link: palette?.link,
    },
    fallback,
  );
}

export function transformThemeConfig(config: ThemeConfigResponse | null | undefined): ThemeConfig {
  return {
    light: transformThemePalette(config?.light, CLASSIC_LIGHT_PALETTE),
    dark: transformThemePalette(config?.dark, CLASSIC_DARK_PALETTE),
  };
}

function serializeThemePalette(palette: ThemePalette): ThemePaletteResponse {
  return {
    background: palette.background,
    sidebar_background: palette.sidebarBackground,
    panel_background: palette.panelBackground,
    editor_background: palette.editorBackground,
    input_background: palette.inputBackground,
    foreground: palette.foreground,
    muted_foreground: palette.mutedForeground,
    border: palette.border,
    border_subtle: palette.borderSubtle,
    hover_background: palette.hoverBackground,
    selection_background: palette.selectionBackground,
    selection_foreground: palette.selectionForeground,
    accent: palette.accent,
    accent_foreground: palette.accentForeground,
    accent_hover: palette.accentHover,
    link: palette.link,
  };
}

export function serializeThemeConfig(config: ThemeConfig): ThemeConfigResponse {
  return {
    light: serializeThemePalette(config.light),
    dark: serializeThemePalette(config.dark),
  };
}

export function normalizeThemePreset(id: string | null | undefined): ThemePresetId {
  if (id === CUSTOM_THEME_PRESET_ID) return CUSTOM_THEME_PRESET_ID;
  if (THEME_PRESETS.some((preset) => preset.id === id)) return id as ThemePresetId;
  return DEFAULT_THEME_PRESET_ID;
}

export function getThemePreset(id: string | null | undefined): ThemePreset {
  const normalizedId = normalizeThemePreset(id);
  return (
    THEME_PRESETS.find((preset) => preset.id === normalizedId) ??
    THEME_PRESETS.find((preset) => preset.id === DEFAULT_THEME_PRESET_ID)!
  );
}

export function resolveThemeConfig(
  presetId: string | null | undefined,
  customConfig: ThemeConfig | null | undefined,
): ThemeConfig {
  if (normalizeThemePreset(presetId) === CUSTOM_THEME_PRESET_ID) {
    return transformThemeConfig(serializeThemeConfig(customConfig ?? DEFAULT_THEME_CONFIG));
  }

  const preset = getThemePreset(presetId);
  return {
    light: { ...preset.light },
    dark: { ...preset.dark },
  };
}

export function resolveThemePalette(
  presetId: string | null | undefined,
  customConfig: ThemeConfig | null | undefined,
  appearance: ThemeAppearance,
): ThemePalette {
  return resolveThemeConfig(presetId, customConfig)[appearance];
}

function mix(color: string, percentage: number, background: string): string {
  return `color-mix(in srgb, ${color} ${percentage}%, ${background})`;
}

function alpha(color: string, percentage: number): string {
  return `color-mix(in srgb, ${color} ${percentage}%, transparent)`;
}

const CLASSIC_LIGHT_GRAY_VARIABLES: Record<string, string> = {
  "--gray-1": "#fcfcfc",
  "--gray-2": "#f9f9f9",
  "--gray-3": "#f0f0f0",
  "--gray-4": "#e8e8e8",
  "--gray-5": "#e0e0e0",
  "--gray-6": "#d9d9d9",
  "--gray-7": "#cecece",
  "--gray-8": "#bbbbbb",
  "--gray-9": "#8d8d8d",
  "--gray-10": "#838383",
  "--gray-11": "#646464",
  "--gray-12": "#202020",
  "--gray-a1": "#00000003",
  "--gray-a2": "#00000006",
  "--gray-a3": "#0000000f",
  "--gray-a4": "#00000017",
  "--gray-a5": "#0000001f",
  "--gray-a6": "#00000026",
  "--gray-a7": "#00000031",
  "--gray-a8": "#00000044",
  "--gray-a9": "#00000072",
  "--gray-a10": "#0000007c",
  "--gray-a11": "#0000009b",
  "--gray-a12": "#000000df",
  "--gray-surface": "#ffffffcc",
  "--gray-contrast": "white",
  "--gray-indicator": "#8d8d8d",
  "--gray-track": "#8d8d8d",
};

const CLASSIC_DARK_GRAY_VARIABLES: Record<string, string> = {
  "--gray-1": "#111111",
  "--gray-2": "#191919",
  "--gray-3": "#222222",
  "--gray-4": "#2a2a2a",
  "--gray-5": "#313131",
  "--gray-6": "#3a3a3a",
  "--gray-7": "#484848",
  "--gray-8": "#606060",
  "--gray-9": "#6e6e6e",
  "--gray-10": "#7b7b7b",
  "--gray-11": "#b4b4b4",
  "--gray-12": "#eeeeee",
  "--gray-a1": "#00000000",
  "--gray-a2": "#ffffff09",
  "--gray-a3": "#ffffff12",
  "--gray-a4": "#ffffff1b",
  "--gray-a5": "#ffffff22",
  "--gray-a6": "#ffffff2c",
  "--gray-a7": "#ffffff3b",
  "--gray-a8": "#ffffff55",
  "--gray-a9": "#ffffff64",
  "--gray-a10": "#ffffff72",
  "--gray-a11": "#ffffffaf",
  "--gray-a12": "#ffffffed",
  "--gray-surface": "#21212180",
  "--gray-contrast": "white",
  "--gray-indicator": "#6e6e6e",
  "--gray-track": "#6e6e6e",
};

const CLASSIC_LIGHT_ACCENT_VARIABLES: Record<string, string> = {
  "--accent-1": "#fafafa",
  "--accent-2": "#f5f5f5",
  "--accent-3": "#e5e5e5",
  "--accent-4": "#d4d4d4",
  "--accent-5": "#a3a3a3",
  "--accent-6": "#737373",
  "--accent-7": "#525252",
  "--accent-8": "#404040",
  "--accent-9": "#000000",
  "--accent-10": "#1a1a1a",
  "--accent-11": "#000000",
  "--accent-12": "#000000",
  "--accent-a1": "rgba(0, 0, 0, 0.02)",
  "--accent-a2": "rgba(0, 0, 0, 0.05)",
  "--accent-a3": "rgba(0, 0, 0, 0.1)",
  "--accent-a4": "rgba(0, 0, 0, 0.15)",
  "--accent-a5": "rgba(0, 0, 0, 0.3)",
  "--accent-a6": "rgba(0, 0, 0, 0.45)",
  "--accent-a7": "rgba(0, 0, 0, 0.6)",
  "--accent-a8": "rgba(0, 0, 0, 0.75)",
  "--accent-a9": "rgba(0, 0, 0, 0.95)",
  "--accent-a10": "rgba(0, 0, 0, 0.98)",
  "--accent-a11": "rgba(0, 0, 0, 1)",
  "--accent-a12": "rgba(0, 0, 0, 1)",
  "--accent-contrast": "#ffffff",
  "--accent-surface": "#ffffffcc",
  "--accent-indicator": "#8d8d8d",
  "--accent-track": "#8d8d8d",
};

const CLASSIC_DARK_ACCENT_VARIABLES: Record<string, string> = {
  "--accent-1": "#0a0a0a",
  "--accent-2": "#1a1a1a",
  "--accent-3": "#262626",
  "--accent-4": "#333333",
  "--accent-5": "#525252",
  "--accent-6": "#737373",
  "--accent-7": "#a3a3a3",
  "--accent-8": "#d4d4d4",
  "--accent-9": "#ffffff",
  "--accent-10": "#f5f5f5",
  "--accent-11": "#ffffff",
  "--accent-12": "#ffffff",
  "--accent-a1": "rgba(255, 255, 255, 0.02)",
  "--accent-a2": "rgba(255, 255, 255, 0.05)",
  "--accent-a3": "rgba(255, 255, 255, 0.1)",
  "--accent-a4": "rgba(255, 255, 255, 0.15)",
  "--accent-a5": "rgba(255, 255, 255, 0.3)",
  "--accent-a6": "rgba(255, 255, 255, 0.45)",
  "--accent-a7": "rgba(255, 255, 255, 0.6)",
  "--accent-a8": "rgba(255, 255, 255, 0.75)",
  "--accent-a9": "rgba(255, 255, 255, 0.95)",
  "--accent-a10": "rgba(255, 255, 255, 0.98)",
  "--accent-a11": "rgba(255, 255, 255, 1)",
  "--accent-a12": "rgba(255, 255, 255, 1)",
  "--accent-contrast": "#000000",
  "--accent-surface": "#21212180",
  "--accent-indicator": "#6e6e6e",
  "--accent-track": "#6e6e6e",
};

function buildThemeVariables(palette: ThemePalette): Record<string, string> {
  const grayAlphaPercentages = [2, 4, 8, 12, 18, 26, 34, 44, 56, 64, 78, 90];
  const accentAlphaPercentages = [4, 8, 14, 20, 28, 36, 46, 58, 72, 80, 88, 94];
  const isClassicLight = palette.background === "#ffffff" && palette.accent === "#000000";
  const isClassicDark = palette.background === "#111111" && palette.accent === "#ffffff";
  const grayVariables: Record<string, string> = isClassicLight
    ? { ...CLASSIC_LIGHT_GRAY_VARIABLES }
    : isClassicDark
      ? { ...CLASSIC_DARK_GRAY_VARIABLES }
      : {
          "--gray-1": palette.background,
          "--gray-2": palette.panelBackground,
          "--gray-3": palette.hoverBackground,
          "--gray-4": palette.hoverBackground,
          "--gray-5": palette.borderSubtle,
          "--gray-6": palette.border,
          "--gray-7": palette.border,
          "--gray-8": mix(palette.mutedForeground, 72, palette.foreground),
          "--gray-9": palette.mutedForeground,
          "--gray-10": palette.mutedForeground,
          "--gray-11": palette.mutedForeground,
          "--gray-12": palette.foreground,
          "--gray-surface": mix(palette.panelBackground, 88, "transparent"),
          "--gray-contrast": palette.accentForeground,
          "--gray-indicator": palette.border,
          "--gray-track": palette.border,
        };

  if (!isClassicLight && !isClassicDark) {
    grayAlphaPercentages.forEach((percentage, index) => {
      grayVariables[`--gray-a${index + 1}`] = alpha(palette.foreground, percentage);
    });
  }

  const accentVariables: Record<string, string> = isClassicLight
    ? { ...CLASSIC_LIGHT_ACCENT_VARIABLES }
    : isClassicDark
      ? { ...CLASSIC_DARK_ACCENT_VARIABLES }
      : {
          "--accent-1": mix(palette.accent, 5, palette.background),
          "--accent-2": mix(palette.accent, 10, palette.background),
          "--accent-3": mix(palette.accent, 18, palette.background),
          "--accent-4": mix(palette.accent, 26, palette.background),
          "--accent-5": mix(palette.accent, 36, palette.background),
          "--accent-6": mix(palette.accent, 46, palette.background),
          "--accent-7": mix(palette.accent, 58, palette.background),
          "--accent-8": mix(palette.accent, 72, palette.background),
          "--accent-9": palette.accent,
          "--accent-10": palette.accentHover,
          "--accent-11": palette.accentHover,
          "--accent-12": mix(palette.accent, 42, palette.foreground),
          "--accent-contrast": palette.accentForeground,
          "--accent-surface": mix(palette.accent, 12, palette.panelBackground),
          "--accent-indicator": palette.accent,
          "--accent-track": palette.accent,
        };

  if (!isClassicLight && !isClassicDark) {
    accentAlphaPercentages.forEach((percentage, index) => {
      accentVariables[`--accent-a${index + 1}`] = alpha(palette.accent, percentage);
    });
  }

  const colorVariables = isClassicLight
    ? {
        "--color-panel-translucent": "rgba(255, 255, 255, 0.7)",
        "--color-surface": "rgba(255, 255, 255, 0.85)",
        "--color-overlay": "rgba(0, 0, 0, 0.4)",
      }
    : isClassicDark
      ? {
          "--color-panel-translucent": "#ffffff09",
          "--color-surface": "rgba(0, 0, 0, 0.25)",
          "--color-overlay": "rgba(0, 0, 0, 0.6)",
        }
      : {
          "--color-panel-translucent": mix(palette.panelBackground, 86, "transparent"),
          "--color-surface": palette.inputBackground,
          "--color-overlay": alpha("#000000", 48),
        };

  return {
    "--theme-background": palette.background,
    "--theme-sidebar-background": palette.sidebarBackground,
    "--theme-panel-background": palette.panelBackground,
    "--theme-editor-background": palette.editorBackground,
    "--theme-input-background": palette.inputBackground,
    "--theme-foreground": palette.foreground,
    "--theme-muted-foreground": palette.mutedForeground,
    "--theme-border": palette.border,
    "--theme-border-subtle": palette.borderSubtle,
    "--theme-hover-background": palette.hoverBackground,
    "--theme-selection-background": palette.selectionBackground,
    "--theme-selection-foreground": palette.selectionForeground,
    "--theme-accent": palette.accent,
    "--theme-accent-foreground": palette.accentForeground,
    "--theme-accent-hover": palette.accentHover,
    "--theme-link": palette.link,
    "--color-background": palette.background,
    "--color-panel-solid": palette.panelBackground,
    ...colorVariables,
    ...grayVariables,
    ...accentVariables,
  };
}

const appliedThemeVariables = new WeakMap<HTMLElement, Record<string, string>>();
let activeThemePalette: ThemePalette | null = null;

export function applyThemePalette(palette: ThemePalette): void {
  activeThemePalette = palette;
  if (typeof document === "undefined") return;

  const variables = buildThemeVariables(palette);
  const elements = [
    document.documentElement,
    ...document.querySelectorAll<HTMLElement>(".radix-themes"),
  ];

  elements.forEach((element) => {
    const previousVariables = appliedThemeVariables.get(element);
    Object.entries(variables).forEach(([name, value]) => {
      if (previousVariables?.[name] === value) return;
      element.style.setProperty(name, value);
    });
    appliedThemeVariables.set(element, variables);
  });
}

export function observeThemeRoots(): () => void {
  if (
    typeof document === "undefined" ||
    typeof MutationObserver === "undefined" ||
    !document.body
  ) {
    return () => undefined;
  }

  const observer = new MutationObserver((mutations) => {
    const hasNewThemeRoot = mutations.some((mutation) =>
      Array.from(mutation.addedNodes).some(
        (node) =>
          node instanceof Element &&
          (node.matches(".radix-themes") || node.querySelector(".radix-themes") !== null),
      ),
    );
    const palette = activeThemePalette;

    if (!hasNewThemeRoot || !palette) return;
    applyThemePalette(palette);
  });

  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}
