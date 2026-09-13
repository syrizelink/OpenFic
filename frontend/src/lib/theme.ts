import { generateRadixColors } from "./radix-color-generator";

export interface ThemePalette {
  accent: string;
  gray: string;
  background: string;
}

export interface ThemeConfig {
  light: ThemePalette;
  dark: ThemePalette;
}

export interface ThemePaletteResponse {
  accent?: string;
  gray?: string;
  background?: string;
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
  availableAppearances: readonly ThemeAppearance[];
  labelKeyByAppearance?: Partial<Record<ThemeAppearance, string>>;
  light: ThemePalette;
  dark: ThemePalette;
}

export const DEFAULT_THEME_PRESET_ID = "classic" as const;
export const CUSTOM_THEME_PRESET_ID = "custom" as const;

const CLASSIC_LIGHT_PALETTE: ThemePalette = {
  accent: "#000000",
  gray: "#646464",
  background: "#ffffff",
};

const CLASSIC_DARK_PALETTE: ThemePalette = {
  accent: "#ffffff",
  gray: "#b4b4b4",
  background: "#111111",
};

const VSCODE_DARK_PALETTE: ThemePalette = {
  accent: "#007acc",
  gray: "#9d9d9d",
  background: "#1e1e1e",
};

const SOLARIZED_LIGHT_PALETTE: ThemePalette = {
  accent: "#268bd2",
  gray: "#839496",
  background: "#fdf6e3",
};

const SOLARIZED_DARK_PALETTE: ThemePalette = {
  accent: "#268bd2",
  gray: "#839496",
  background: "#002b36",
};

const NORD_LIGHT_PALETTE: ThemePalette = {
  accent: "#5e81ac",
  gray: "#5e81ac",
  background: "#eceff4",
};

const NORD_DARK_PALETTE: ThemePalette = {
  accent: "#88c0d0",
  gray: "#5e81ac",
  background: "#2e3440",
};

const MONOKAI_LIGHT_PALETTE: ThemePalette = {
  accent: "#66a80f",
  gray: "#75715e",
  background: "#faf8f2",
};

const MONOKAI_DARK_PALETTE: ThemePalette = {
  accent: "#a6e22e",
  gray: "#a6a6a0",
  background: "#272822",
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
    availableAppearances: ["light", "dark"],
    labelKeyByAppearance: { dark: "settings.themePresetClassicDark" },
    light: CLASSIC_LIGHT_PALETTE,
    dark: CLASSIC_DARK_PALETTE,
  },
  {
    id: "vscode-dark",
    labelKey: "settings.themePresetVSCode",
    defaultAppearance: "dark",
    availableAppearances: ["dark"],
    light: CLASSIC_LIGHT_PALETTE,
    dark: VSCODE_DARK_PALETTE,
  },
  {
    id: "solarized",
    labelKey: "settings.themePresetSolarized",
    defaultAppearance: "light",
    availableAppearances: ["light", "dark"],
    labelKeyByAppearance: { dark: "settings.themePresetSolarizedDark" },
    light: SOLARIZED_LIGHT_PALETTE,
    dark: SOLARIZED_DARK_PALETTE,
  },
  {
    id: "nord",
    labelKey: "settings.themePresetNord",
    defaultAppearance: "dark",
    availableAppearances: ["light", "dark"],
    labelKeyByAppearance: { dark: "settings.themePresetNordDark" },
    light: NORD_LIGHT_PALETTE,
    dark: NORD_DARK_PALETTE,
  },
  {
    id: "monokai",
    labelKey: "settings.themePresetMonokai",
    defaultAppearance: "dark",
    availableAppearances: ["light", "dark"],
    labelKeyByAppearance: { dark: "settings.themePresetMonokaiDark" },
    light: MONOKAI_LIGHT_PALETTE,
    dark: MONOKAI_DARK_PALETTE,
  },
] as const satisfies readonly ThemePreset[];

export const CUSTOM_THEME_PRESET = {
  id: CUSTOM_THEME_PRESET_ID,
  labelKey: "settings.themePresetCustom",
  defaultAppearance: "light",
  availableAppearances: ["light", "dark"],
  light: CLASSIC_LIGHT_PALETTE,
  dark: CLASSIC_DARK_PALETTE,
} as const satisfies ThemePreset;

export type ThemePresetId = (typeof THEME_PRESETS)[number]["id"] | typeof CUSTOM_THEME_PRESET_ID;
export type ThemeAppearance = "light" | "dark";

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
    accent: normalizeColor(palette?.accent, fallback.accent),
    gray: normalizeColor(palette?.gray, fallback.gray),
    background: normalizeColor(palette?.background, fallback.background),
  };
}

function transformThemePalette(
  palette: ThemePaletteResponse | null | undefined,
  fallback: ThemePalette,
): ThemePalette {
  return normalizeThemePalette(
    {
      accent: palette?.accent,
      gray: palette?.gray,
      background: palette?.background,
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
    accent: palette.accent,
    gray: palette.gray,
    background: palette.background,
  };
}

export function serializeThemeConfig(config: ThemeConfig): ThemeConfigResponse {
  return {
    light: serializeThemePalette(config.light),
    dark: serializeThemePalette(config.dark),
  };
}

export function normalizeThemePreset(
  id: string | null | undefined,
  appearance?: ThemeAppearance,
): ThemePresetId {
  if (id === CUSTOM_THEME_PRESET_ID) return CUSTOM_THEME_PRESET_ID;
  const preset = THEME_PRESETS.find((item) => item.id === id);
  if (!preset) return DEFAULT_THEME_PRESET_ID;
  if (appearance && !preset.availableAppearances.some((item) => item === appearance)) {
    return DEFAULT_THEME_PRESET_ID;
  }
  return preset.id as ThemePresetId;
}

export function getThemePresetsForAppearance(appearance: ThemeAppearance): readonly ThemePreset[] {
  return THEME_PRESETS.filter((preset) =>
    preset.availableAppearances.some((item) => item === appearance),
  );
}

export function getThemePresetLabelKey(preset: ThemePreset, appearance: ThemeAppearance): string {
  return preset.labelKeyByAppearance?.[appearance] ?? preset.labelKey;
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

function createRadixScaleVariables(
  name: string,
  scale: readonly string[],
  alphaScale: readonly string[],
  extras: Record<string, string>,
): Record<string, string> {
  const variables: Record<string, string> = { ...extras };

  scale.forEach((value, index) => {
    variables[`--${name}-${index + 1}`] = value;
  });
  alphaScale.forEach((value, index) => {
    variables[`--${name}-a${index + 1}`] = value;
  });

  return variables;
}

const CLASSIC_LIGHT_GRAY_VARIABLES = createRadixScaleVariables(
  "gray",
  [
    "#fcfcfc",
    "#f9f9f9",
    "#f0f0f0",
    "#e8e8e8",
    "#e0e0e0",
    "#d9d9d9",
    "#cecece",
    "#bbbbbb",
    "#8d8d8d",
    "#838383",
    "#646464",
    "#202020",
  ],
  [
    "#00000003",
    "#00000006",
    "#0000000f",
    "#00000017",
    "#0000001f",
    "#00000026",
    "#00000031",
    "#00000044",
    "#00000072",
    "#0000007c",
    "#0000009b",
    "#000000df",
  ],
  {
    "--gray-surface": "#ffffffcc",
    "--gray-contrast": "white",
    "--gray-indicator": "#8d8d8d",
    "--gray-track": "#8d8d8d",
  },
);

const CLASSIC_DARK_GRAY_VARIABLES = createRadixScaleVariables(
  "gray",
  [
    "#111111",
    "#191919",
    "#222222",
    "#2a2a2a",
    "#313131",
    "#3a3a3a",
    "#484848",
    "#606060",
    "#6e6e6e",
    "#7b7b7b",
    "#b4b4b4",
    "#eeeeee",
  ],
  [
    "#00000000",
    "#ffffff09",
    "#ffffff12",
    "#ffffff1b",
    "#ffffff22",
    "#ffffff2c",
    "#ffffff3b",
    "#ffffff55",
    "#ffffff64",
    "#ffffff72",
    "#ffffffaf",
    "#ffffffed",
  ],
  {
    "--gray-surface": "#21212180",
    "--gray-contrast": "white",
    "--gray-indicator": "#6e6e6e",
    "--gray-track": "#6e6e6e",
  },
);

const CLASSIC_LIGHT_ACCENT_VARIABLES = createRadixScaleVariables(
  "accent",
  [
    "#fafafa",
    "#f5f5f5",
    "#e5e5e5",
    "#d4d4d4",
    "#a3a3a3",
    "#737373",
    "#525252",
    "#404040",
    "#000000",
    "#1a1a1a",
    "#000000",
    "#000000",
  ],
  [
    "rgba(0, 0, 0, 0.02)",
    "rgba(0, 0, 0, 0.05)",
    "rgba(0, 0, 0, 0.1)",
    "rgba(0, 0, 0, 0.15)",
    "rgba(0, 0, 0, 0.3)",
    "rgba(0, 0, 0, 0.45)",
    "rgba(0, 0, 0, 0.6)",
    "rgba(0, 0, 0, 0.75)",
    "rgba(0, 0, 0, 0.95)",
    "rgba(0, 0, 0, 0.98)",
    "rgba(0, 0, 0, 1)",
    "rgba(0, 0, 0, 1)",
  ],
  {
    "--accent-contrast": "#ffffff",
    "--accent-surface": "#ffffffcc",
    "--accent-indicator": "#8d8d8d",
    "--accent-track": "#8d8d8d",
  },
);

const CLASSIC_DARK_ACCENT_VARIABLES = createRadixScaleVariables(
  "accent",
  [
    "#0a0a0a",
    "#1a1a1a",
    "#262626",
    "#333333",
    "#525252",
    "#737373",
    "#a3a3a3",
    "#d4d4d4",
    "#ffffff",
    "#f5f5f5",
    "#ffffff",
    "#ffffff",
  ],
  [
    "rgba(255, 255, 255, 0.02)",
    "rgba(255, 255, 255, 0.05)",
    "rgba(255, 255, 255, 0.1)",
    "rgba(255, 255, 255, 0.15)",
    "rgba(255, 255, 255, 0.3)",
    "rgba(255, 255, 255, 0.45)",
    "rgba(255, 255, 255, 0.6)",
    "rgba(255, 255, 255, 0.75)",
    "rgba(255, 255, 255, 0.95)",
    "rgba(255, 255, 255, 0.98)",
    "rgba(255, 255, 255, 1)",
    "rgba(255, 255, 255, 1)",
  ],
  {
    "--accent-contrast": "#000000",
    "--accent-surface": "#21212180",
    "--accent-indicator": "#6e6e6e",
    "--accent-track": "#6e6e6e",
  },
);

const CLASSIC_LIGHT_THEME_VARIABLES: Record<string, string> = {
  "--theme-background": "#ffffff",
  "--theme-sidebar-background": "#ffffff",
  "--theme-panel-background": "#ffffff",
  "--theme-editor-background": "#ffffff",
  "--theme-editor-bar-background": "var(--gray-a2)",
  "--theme-status-bar-background": "var(--gray-2)",
  "--theme-input-background": "#ffffff",
  "--theme-foreground": "#202020",
  "--theme-muted-foreground": "#646464",
  "--theme-border": "#d9d9d9",
  "--theme-border-subtle": "#e8e8e8",
  "--theme-hover-background": "#f0f0f0",
  "--theme-list-hover-background": "var(--gray-a2)",
  "--theme-selection-background": "#e5e5e5",
  "--theme-selection-foreground": "#202020",
  "--theme-accent": "#000000",
  "--theme-accent-foreground": "#ffffff",
  "--theme-accent-hover": "#1a1a1a",
  "--theme-link": "#0969da",
  "--theme-link-hover": "#0550ae",
  "--color-background": "#ffffff",
  "--color-panel-solid": "#ffffff",
  "--color-panel-translucent": "rgba(255, 255, 255, 0.7)",
  "--color-surface": "rgba(255, 255, 255, 0.85)",
  "--color-overlay": "rgba(0, 0, 0, 0.4)",
};

const CLASSIC_DARK_THEME_VARIABLES: Record<string, string> = {
  "--theme-background": "#111111",
  "--theme-sidebar-background": "#111111",
  "--theme-panel-background": "#191919",
  "--theme-editor-background": "#111111",
  "--theme-editor-bar-background": "var(--gray-a2)",
  "--theme-status-bar-background": "var(--gray-2)",
  "--theme-input-background": "#191919",
  "--theme-foreground": "#eeeeee",
  "--theme-muted-foreground": "#b4b4b4",
  "--theme-border": "#3a3a3a",
  "--theme-border-subtle": "#2a2a2a",
  "--theme-hover-background": "#222222",
  "--theme-list-hover-background": "var(--gray-a2)",
  "--theme-selection-background": "#262626",
  "--theme-selection-foreground": "#eeeeee",
  "--theme-accent": "#ffffff",
  "--theme-accent-foreground": "#000000",
  "--theme-accent-hover": "#f5f5f5",
  "--theme-link": "#0969da",
  "--theme-link-hover": "#0550ae",
  "--color-background": "#111111",
  "--color-panel-solid": "#191919",
  "--color-panel-translucent": "#ffffff09",
  "--color-surface": "rgba(0, 0, 0, 0.25)",
  "--color-overlay": "rgba(0, 0, 0, 0.6)",
};

function supportsColor(value: string): boolean {
  return (
    typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports("color", value)
  );
}

function getGeneratedVariables(
  palette: ThemePalette,
  appearance: ThemeAppearance,
): Record<string, string> {
  const generated = generateRadixColors({
    appearance,
    accent: palette.accent,
    gray: palette.gray,
    background: palette.background,
  });
  const useWideGamut =
    supportsColor(generated.accentScaleWideGamut[0]) &&
    supportsColor(generated.grayScaleWideGamut[0]) &&
    supportsColor(generated.accentScaleAlphaWideGamut[0]);
  const accentScale = useWideGamut ? generated.accentScaleWideGamut : generated.accentScale;
  const accentScaleAlpha = useWideGamut
    ? generated.accentScaleAlphaWideGamut
    : generated.accentScaleAlpha;
  const grayScale = useWideGamut ? generated.grayScaleWideGamut : generated.grayScale;
  const grayScaleAlpha = useWideGamut
    ? generated.grayScaleAlphaWideGamut
    : generated.grayScaleAlpha;
  const backgroundScale = useWideGamut
    ? generated.backgroundScaleWideGamut
    : generated.backgroundScale;
  const backgroundScaleAlpha = useWideGamut
    ? generated.backgroundScaleAlphaWideGamut
    : generated.backgroundScaleAlpha;
  const graySurface = useWideGamut ? generated.graySurfaceWideGamut : generated.graySurface;
  const accentSurface = useWideGamut ? generated.accentSurfaceWideGamut : generated.accentSurface;

  const grayVariables = createRadixScaleVariables("gray", grayScale, grayScaleAlpha, {
    "--gray-contrast": "#ffffff",
    "--gray-surface": graySurface,
    "--gray-indicator": grayScale[8],
    "--gray-track": grayScale[8],
  });
  const accentVariables = createRadixScaleVariables("accent", accentScale, accentScaleAlpha, {
    "--accent-contrast": generated.accentContrast,
    "--accent-surface": accentSurface,
    "--accent-indicator": accentScale[8],
    "--accent-track": accentScale[8],
  });

  return {
    ...grayVariables,
    ...accentVariables,
    "--theme-background": generated.background,
    "--theme-sidebar-background": backgroundScale[1],
    "--theme-panel-background": backgroundScale[1],
    "--theme-editor-background": generated.background,
    "--theme-editor-bar-background": backgroundScale[1],
    "--theme-status-bar-background": backgroundScale[1],
    "--theme-input-background": backgroundScale[2],
    "--theme-foreground": grayScale[11],
    "--theme-muted-foreground": grayScale[10],
    "--theme-border": grayScale[5],
    "--theme-border-subtle": grayScale[4],
    "--theme-hover-background": backgroundScale[3],
    "--theme-list-hover-background": backgroundScale[2],
    "--theme-selection-background": accentScaleAlpha[3],
    "--theme-selection-foreground": grayScale[11],
    "--theme-accent": accentScale[8],
    "--theme-accent-foreground": generated.accentContrast,
    "--theme-accent-hover": accentScale[9],
    "--theme-link": accentScale[10],
    "--theme-link-hover": accentScale[9],
    "--color-background": generated.background,
    "--color-panel-solid": backgroundScale[1],
    "--color-panel-translucent": backgroundScaleAlpha[1],
    "--color-surface": backgroundScale[2],
    "--color-overlay": "rgba(0, 0, 0, 0.48)",
  };
}

function buildThemeVariables(
  palette: ThemePalette,
  appearance: ThemeAppearance,
  presetId: ThemePresetId,
): Record<string, string> {
  const classicPalette = appearance === "dark" ? CLASSIC_DARK_PALETTE : CLASSIC_LIGHT_PALETTE;
  if (
    presetId === DEFAULT_THEME_PRESET_ID ||
    (palette.accent === classicPalette.accent &&
      palette.gray === classicPalette.gray &&
      palette.background === classicPalette.background)
  ) {
    return {
      ...(appearance === "dark" ? CLASSIC_DARK_THEME_VARIABLES : CLASSIC_LIGHT_THEME_VARIABLES),
      ...(appearance === "dark" ? CLASSIC_DARK_GRAY_VARIABLES : CLASSIC_LIGHT_GRAY_VARIABLES),
      ...(appearance === "dark" ? CLASSIC_DARK_ACCENT_VARIABLES : CLASSIC_LIGHT_ACCENT_VARIABLES),
    };
  }

  return getGeneratedVariables(palette, appearance);
}

interface ActiveTheme {
  palette: ThemePalette;
  appearance: ThemeAppearance;
  presetId: ThemePresetId;
}

const appliedThemeVariables = new WeakMap<HTMLElement, Record<string, string>>();
let activeTheme: ActiveTheme | null = null;

export function applyThemePalette(
  palette: ThemePalette,
  appearance: ThemeAppearance,
  presetId: ThemePresetId,
): void {
  activeTheme = { palette, appearance, presetId };
  if (typeof document === "undefined") return;

  const variables = buildThemeVariables(palette, appearance, presetId);
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
    const theme = activeTheme;

    if (!hasNewThemeRoot || !theme) return;
    applyThemePalette(theme.palette, theme.appearance, theme.presetId);
  });

  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}
