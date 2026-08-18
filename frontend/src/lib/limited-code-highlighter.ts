import type {
  CodeHighlighterPlugin,
  HighlightOptions,
  HighlightResult,
  ThemeInput,
} from "@streamdown/code";
import { createBundledHighlighter } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";

const LANGUAGE_LOADERS = {
  bash: () => import("shiki/langs/bash"),
  css: () => import("shiki/langs/css"),
  diff: () => import("shiki/langs/diff"),
  html: () => import("shiki/langs/html"),
  javascript: () => import("shiki/langs/javascript"),
  json: () => import("shiki/langs/json"),
  jsx: () => import("shiki/langs/jsx"),
  markdown: () => import("shiki/langs/markdown"),
  python: () => import("shiki/langs/python"),
  sql: () => import("shiki/langs/sql"),
  tsx: () => import("shiki/langs/tsx"),
  typescript: () => import("shiki/langs/typescript"),
  yaml: () => import("shiki/langs/yaml"),
};

const THEME_LOADERS = {
  "github-dark": () => import("shiki/themes/github-dark"),
  "github-light": () => import("shiki/themes/github-light"),
};

export const SUPPORTED_CODE_LANGUAGES = Object.keys(LANGUAGE_LOADERS) as Array<
  keyof typeof LANGUAGE_LOADERS
>;

const LANGUAGE_ALIASES: Record<string, keyof typeof LANGUAGE_LOADERS> = {
  js: "javascript",
  md: "markdown",
  py: "python",
  sh: "bash",
  shell: "bash",
  ts: "typescript",
  yml: "yaml",
};

const DEFAULT_THEMES = ["github-light", "github-dark"] as const;
type SupportedLanguage = (typeof SUPPORTED_CODE_LANGUAGES)[number];
type SupportedTheme = (typeof DEFAULT_THEMES)[number];
type CustomTheme = Exclude<ThemeInput, string>;
type ResolvedTheme = SupportedTheme | CustomTheme;

const createHighlighter = createBundledHighlighter({
  engine: () => createJavaScriptRegexEngine({ forgiving: true }),
  langs: LANGUAGE_LOADERS,
  themes: THEME_LOADERS,
});

const highlighterCache = new Map<string, ReturnType<typeof createHighlighter>>();
const highlightCache = new Map<string, HighlightResult>();
const pendingHighlightCache = new Map<string, Promise<HighlightResult>>();
const customThemeIds = new WeakMap<object, number>();
let nextCustomThemeId = 0;

function resolveLanguage(language: string): SupportedLanguage | null {
  const normalized = language.trim().toLowerCase();
  if (Object.hasOwn(LANGUAGE_LOADERS, normalized)) return normalized as SupportedLanguage;
  return Object.hasOwn(LANGUAGE_ALIASES, normalized) ? LANGUAGE_ALIASES[normalized] : null;
}

function resolveTheme(theme: ThemeInput, fallback: SupportedTheme): ResolvedTheme {
  if (typeof theme !== "string") return theme;
  if (Object.hasOwn(THEME_LOADERS, theme)) return theme as SupportedTheme;
  return fallback;
}

function getThemeKey(theme: ResolvedTheme): string {
  if (typeof theme === "string") return theme;

  const existingId = customThemeIds.get(theme);
  if (existingId) return `custom-${existingId}`;

  nextCustomThemeId += 1;
  customThemeIds.set(theme, nextCustomThemeId);
  return `custom-${nextCustomThemeId}`;
}

function getHighlighter(language: SupportedLanguage, themes: [ResolvedTheme, ResolvedTheme]) {
  const cacheKey = `${language}:${themes.map(getThemeKey).join(":")}`;
  const cached = highlighterCache.get(cacheKey);
  if (cached) return cached;

  const highlighter = createHighlighter({ langs: [language], themes });
  highlighterCache.set(cacheKey, highlighter);
  return highlighter;
}

function createHighlightKey(
  code: string,
  language: SupportedLanguage,
  themes: [ResolvedTheme, ResolvedTheme],
): string {
  return `${language}:${themes.map(getThemeKey).join(":")}:${code}`;
}

function highlightCode(
  options: HighlightOptions,
  callback?: (result: HighlightResult) => void,
): HighlightResult | null {
  const language = resolveLanguage(options.language);
  if (!language) return null;

  const themes: [ResolvedTheme, ResolvedTheme] = [
    resolveTheme(options.themes[0], DEFAULT_THEMES[0]),
    resolveTheme(options.themes[1], DEFAULT_THEMES[1]),
  ];
  const cacheKey = createHighlightKey(options.code, language, themes);
  const cached = highlightCache.get(cacheKey);
  if (cached) return cached;

  const pending = pendingHighlightCache.get(cacheKey);
  if (pending) {
    void pending.then((result) => callback?.(result));
    return null;
  }

  const promise = getHighlighter(language, themes).then((highlighter) => {
    const result = highlighter.codeToTokens(options.code, {
      lang: language,
      themes: { dark: themes[1], light: themes[0] },
    });
    highlightCache.set(cacheKey, result);
    return result;
  });
  pendingHighlightCache.set(cacheKey, promise);
  void promise
    .then((result) => callback?.(result))
    .catch((error) => console.error("[OpenFic Code] Failed to highlight code:", error))
    .finally(() => pendingHighlightCache.delete(cacheKey));
  return null;
}

export function createLimitedCodePlugin(): CodeHighlighterPlugin {
  return {
    name: "shiki",
    type: "code-highlighter",
    getSupportedLanguages: () => [...SUPPORTED_CODE_LANGUAGES],
    getThemes: () => [...DEFAULT_THEMES],
    supportsLanguage: (language) => resolveLanguage(language) !== null,
    highlight: highlightCode,
  };
}
