import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { BrowserRouter, Routes, Route } from "react-router";

import App from "./App.tsx";
import { AppCrashFallback, GlobalLoading, toast } from "./components";
import { Toaster } from "./components/toaster";
import { AppLayout } from "./features/app-shell";
import { AuthPage } from "./features/auth";
import { CharactersPage } from "./features/characters";
import { PromptChainsPage } from "./features/prompt-chains";
import { fetchSettings, updateSettings } from "./features/settings/lib/settings-api";
import type { Settings } from "./features/settings/lib/settings.types";
import { WorldInfoPage } from "./features/world-info";
import { WritingPage } from "./features/writing";
// 初始化 i18n
import i18n, { type LanguageCode } from "./i18n";
import { checkHealth, fetchAuthPreferences, fetchAuthStatus } from "./lib/api-client";
import { publishDesktopAppearance, publishDesktopLanguage } from "./lib/desktop-appearance-bridge";
import {
  applyBaseFontSize,
  applyCodeFontFamily,
  applyEditorFontSize,
  applyFontFamily,
  loadConfiguredFonts,
} from "./lib/font-utils";
import { getOrCreateRoot } from "./lib/get-or-create-root";
import { captureException, initErrorTelemetry } from "./lib/posthog";
import { loadRuntimeConfig } from "./lib/runtime-config";
import { connectSocket } from "./lib/socket-client";
import {
  applyThemePalette,
  DEFAULT_THEME_CONFIG,
  DEFAULT_THEME_PRESET_ID,
  normalizeThemeMode,
  normalizeThemePreset,
  observeThemeRoots,
  resolveThemeAppearance,
  resolveThemePalette,
  resolveThemeVariables,
  transformThemeConfig,
  type ThemeConfig,
  type ThemeAppearance,
  type ThemeMode,
  type ThemePresetId,
  type ThemeSettings,
} from "./lib/theme";
import { preloadTiktokenEncoding } from "./lib/tiktoken-utils";

import "streamdown/styles.css";
import "@fontsource-variable/cascadia-code";
import "@fontsource-variable/fira-code";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/noto-sans-sc";
import "@fontsource-variable/noto-serif-sc";
import "@fontsource-variable/roboto-mono";
import "@fontsource-variable/source-code-pro";
import "@fontsource/ma-shan-zheng";
import "@fontsource/wdxl-lubrifont-sc";
import "@fontsource/zcool-kuaile";
import "@fontsource/zcool-xiaowei";

import "./styles/index.css";

import { registerSW } from "./pwa/register-sw";

/* oxlint-disable react-refresh/only-export-components */
// 创建 QueryClient 实例（保持在组件外部以避免重新创建）
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 分钟
      retry: 1,
    },
  },
});

const FRONTEND_VERSION = __OPENFIC_FRONTEND_VERSION__;
const INITIALIZATION_TIMEOUT_MS = 30_000;
const THEME_SYNC_DEBOUNCE_MS = 400;
const SYSTEM_THEME_MEDIA_QUERY = "(prefers-color-scheme: dark)";
const THEME_MODE_CYCLE: readonly ThemeMode[] = ["system", "light", "dark"];

function getSystemThemeAppearance(): ThemeAppearance {
  return window.matchMedia(SYSTEM_THEME_MEDIA_QUERY).matches ? "dark" : "light";
}

type InitializationStage = "preferences" | "auth" | "health" | "settings" | "tiktoken" | "socket";

class InitializationError extends Error {
  readonly stage: InitializationStage;
  readonly originalError: unknown;

  constructor(stage: InitializationStage, originalError: unknown) {
    super(getErrorDetail(originalError));
    this.name = "InitializationError";
    this.stage = stage;
    this.originalError = originalError;
  }
}

function getErrorDetail(error: unknown): string {
  if (error instanceof Error) {
    const candidate = error as Error & {
      code?: unknown;
      config?: { baseURL?: unknown; url?: unknown };
      response?: { status?: number; statusText?: unknown };
    };
    const details = [candidate.message || candidate.name];

    if (typeof candidate.code === "string" && candidate.code) {
      details.push(i18n.t("common.initializationErrorCode", { code: candidate.code }));
    }

    if (candidate.response?.status) {
      const statusText =
        typeof candidate.response.statusText === "string" && candidate.response.statusText
          ? ` ${candidate.response.statusText}`
          : "";
      details.push(
        i18n.t("common.initializationHttpStatus", {
          status: candidate.response.status,
          statusText,
        }),
      );
    }

    const baseUrl = typeof candidate.config?.baseURL === "string" ? candidate.config.baseURL : "";
    const requestUrl = typeof candidate.config?.url === "string" ? candidate.config.url : "";
    if (baseUrl || requestUrl) {
      details.push(
        i18n.t("common.initializationAddress", {
          address: `${baseUrl}${requestUrl}`,
        }),
      );
    }

    return details.join(i18n.t("common.errorDetailSeparator"));
  }

  if (typeof error === "string" && error) return error;
  return i18n.t("common.initializationUnknownError");
}

function withInitializationStage<T>(stage: InitializationStage, promise: Promise<T>): Promise<T> {
  return promise.catch((error: unknown) => {
    throw new InitializationError(stage, error);
  });
}

function getInitializationErrorMessage(error: unknown): string {
  if (!(error instanceof InitializationError)) {
    return i18n.t("common.initializationFailedWithReason", {
      reason: getErrorDetail(error),
    });
  }

  const stageLabels: Record<InitializationStage, string> = {
    preferences: i18n.t("common.initializationPreferences"),
    auth: i18n.t("common.initializationAuth"),
    health: i18n.t("common.initializationHealth"),
    settings: i18n.t("common.initializationSettings"),
    tiktoken: i18n.t("common.initializationTiktoken"),
    socket: i18n.t("common.initializationSocket"),
  };

  return i18n.t("common.initializationFailedWithStage", {
    stage: stageLabels[error.stage],
    reason: getErrorDetail(error.originalError),
  });
}

const DashboardPage = lazy(() =>
  import("./features/dashboard/pages/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  })),
);

function AppContent({
  appearance,
  version,
  themeMode,
  setThemeMode,
  setThemeSettings,
  previewThemeSettings,
  toggleTheme,
}: {
  appearance: "light" | "dark";
  version: string;
  themeMode: ThemeMode;
  setThemeMode: (themeMode: ThemeMode) => void;
  setThemeSettings: (settings: ThemeSettings) => void;
  previewThemeSettings: (settings: ThemeSettings) => void;
  toggleTheme: () => void;
}) {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <AppLayout
              appearance={appearance}
              version={version}
              themeMode={themeMode}
              onThemeModeChange={setThemeMode}
              onThemeSettingsChange={setThemeSettings}
              onThemePreviewChange={previewThemeSettings}
              onToggleTheme={toggleTheme}
            />
          }
        >
          <Route
            path="/"
            element={<App />}
          />
          <Route
            path="/projects/:projectId"
            element={<WritingPage />}
          />
          <Route
            path="/world-info"
            element={<WorldInfoPage />}
          />
          <Route
            path="/characters"
            element={<CharactersPage />}
          />
          <Route
            path="/prompt-chains"
            element={<PromptChainsPage />}
          />
          <Route
            path="/dashboard"
            element={
              <Suspense fallback={null}>
                <DashboardPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function Root() {
  const [appearance, setAppearance] = useState<ThemeAppearance>(getSystemThemeAppearance);
  const [themeMode, setThemeMode] = useState<ThemeMode>("light");
  const [lightThemePreset, setLightThemePreset] = useState<ThemePresetId>(DEFAULT_THEME_PRESET_ID);
  const [darkThemePreset, setDarkThemePreset] = useState<ThemePresetId>(DEFAULT_THEME_PRESET_ID);
  const [themeConfig, setThemeConfig] = useState<ThemeConfig>(DEFAULT_THEME_CONFIG);
  const [isReady, setIsReady] = useState(false);
  const [requiresAuthentication, setRequiresAuthentication] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latestThemeModeRef = useRef<ThemeMode>("light");
  const latestSystemAppearanceRef = useRef<ThemeAppearance>(getSystemThemeAppearance());
  const hasLoadedPreferencesRef = useRef(false);
  const themeSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const themePreviewFrameRef = useRef<number | null>(null);

  const cancelThemePreview = useCallback(() => {
    if (themePreviewFrameRef.current === null) return;
    window.cancelAnimationFrame(themePreviewFrameRef.current);
    themePreviewFrameRef.current = null;
  }, []);

  const applyThemeMode = useCallback(
    (next: ThemeMode, resolvedAppearance?: ThemeAppearance) => {
      cancelThemePreview();
      const nextAppearance =
        resolvedAppearance ?? resolveThemeAppearance(next, latestSystemAppearanceRef.current);
      latestThemeModeRef.current = next;
      setThemeMode(next);
      setAppearance(nextAppearance);
    },
    [cancelThemePreview],
  );

  const applyThemeSettings = useCallback(
    (next: {
      theme: string;
      themePreset?: string;
      lightThemePreset?: string;
      darkThemePreset?: string;
      themeConfig?: ThemeConfig;
    }) => {
      cancelThemePreview();
      const nextThemeMode = normalizeThemeMode(next.theme);
      const nextAppearance = resolveThemeAppearance(
        nextThemeMode,
        latestSystemAppearanceRef.current,
      );
      const legacyPreset = normalizeThemePreset(next.themePreset, nextAppearance);
      latestThemeModeRef.current = nextThemeMode;
      hasLoadedPreferencesRef.current = true;
      setThemeMode(nextThemeMode);
      setAppearance(nextAppearance);
      setLightThemePreset(normalizeThemePreset(next.lightThemePreset ?? legacyPreset, "light"));
      setDarkThemePreset(normalizeThemePreset(next.darkThemePreset ?? legacyPreset, "dark"));
      setThemeConfig(next.themeConfig ?? DEFAULT_THEME_CONFIG);
    },
    [cancelThemePreview],
  );

  const previewThemeSettings = useCallback(
    (next: ThemeSettings) => {
      cancelThemePreview();
      const nextThemeMode = normalizeThemeMode(next.theme);
      const nextAppearance = resolveThemeAppearance(
        nextThemeMode,
        latestSystemAppearanceRef.current,
      );
      const activeThemePreset =
        nextAppearance === "dark" ? next.darkThemePreset : next.lightThemePreset;
      const palette = resolveThemePalette(activeThemePreset, next.themeConfig, nextAppearance);
      const themeVariables = resolveThemeVariables(palette, nextAppearance, activeThemePreset);

      publishDesktopAppearance({
        appearance: nextAppearance,
        themeVariables,
        persist: false,
      });

      themePreviewFrameRef.current = window.requestAnimationFrame(() => {
        themePreviewFrameRef.current = null;
        applyThemePalette(palette, nextAppearance, activeThemePreset);
      });
    },
    [cancelThemePreview],
  );

  const persistThemeMode = useCallback(async () => {
    try {
      const savedSettings = await updateSettings({ theme: latestThemeModeRef.current });
      queryClient.setQueryData<Settings>(["settings"], savedSettings);
      toast.success(i18n.t("settings.saved"));
    } catch (error) {
      // 持久化失败只影响下次启动,不回滚当前外观;之后任意设置保存会自动带上最新主题修正。
      console.warn("Failed to persist theme preference:", error);
    }
  }, []);

  const scheduleThemeModeSync = useCallback(() => {
    if (themeSyncTimerRef.current) clearTimeout(themeSyncTimerRef.current);
    themeSyncTimerRef.current = setTimeout(() => {
      themeSyncTimerRef.current = null;
      void persistThemeMode();
    }, THEME_SYNC_DEBOUNCE_MS);
  }, [persistThemeMode]);

  const toggleTheme = useCallback(() => {
    const currentIndex = THEME_MODE_CYCLE.indexOf(latestThemeModeRef.current);
    const nextMode = THEME_MODE_CYCLE[(currentIndex + 1) % THEME_MODE_CYCLE.length];
    applyThemeMode(nextMode);
    scheduleThemeModeSync();
  }, [applyThemeMode, scheduleThemeModeSync]);

  useEffect(
    () => () => {
      cancelThemePreview();
      if (themeSyncTimerRef.current) clearTimeout(themeSyncTimerRef.current);
    },
    [cancelThemePreview],
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia(SYSTEM_THEME_MEDIA_QUERY);
    const handleSystemThemeChange = (event: MediaQueryListEvent) => {
      const nextSystemAppearance: ThemeAppearance = event.matches ? "dark" : "light";
      latestSystemAppearanceRef.current = nextSystemAppearance;
      if (latestThemeModeRef.current === "system") {
        applyThemeMode("system", nextSystemAppearance);
      }
    };

    latestSystemAppearanceRef.current = mediaQuery.matches ? "dark" : "light";
    mediaQuery.addEventListener("change", handleSystemThemeChange);
    return () => mediaQuery.removeEventListener("change", handleSystemThemeChange);
  }, [applyThemeMode]);

  useEffect(() => observeThemeRoots(), []);

  useEffect(() => {
    let mounted = true;
    let timer: ReturnType<typeof setTimeout>;
    const startTime = Date.now();

    const initializeApp = async () => {
      try {
        await loadRuntimeConfig();
        const [preferences, authStatus] = await Promise.all([
          withInitializationStage("preferences", fetchAuthPreferences()),
          withInitializationStage("auth", fetchAuthStatus()),
        ]);

        applyFontFamily(preferences.font_family);
        applyCodeFontFamily(preferences.code_font_family);
        applyBaseFontSize(preferences.base_font_size);
        applyEditorFontSize(preferences.editor_font_size);
        void loadConfiguredFonts(preferences.font_family, preferences.code_font_family).catch(
          () => undefined,
        );
        if (preferences.language === "zh-CN" || preferences.language === "en") {
          await i18n.changeLanguage(preferences.language);
        }
        if (mounted) {
          applyThemeSettings({
            theme: preferences.theme,
            themePreset: preferences.theme_preset,
            lightThemePreset: preferences.light_theme_preset,
            darkThemePreset: preferences.dark_theme_preset,
            themeConfig: transformThemeConfig(preferences.theme_config),
          });
        }

        if (authStatus.enabled && !authStatus.authenticated) {
          if (mounted) {
            setRequiresAuthentication(true);
            setIsReady(true);
          }
          return;
        }

        void initErrorTelemetry();

        const [, settings] = await Promise.all([
          withInitializationStage("health", checkHealth()),
          withInitializationStage(
            "settings",
            queryClient.fetchQuery({
              queryKey: ["settings"],
              queryFn: fetchSettings,
            }),
          ),
          withInitializationStage("tiktoken", preloadTiktokenEncoding()),
          withInitializationStage(
            "socket",
            connectSocket({ timeoutMs: INITIALIZATION_TIMEOUT_MS }),
          ),
        ]);

        applyFontFamily(settings.fontFamily);
        applyCodeFontFamily(settings.codeFontFamily);
        applyBaseFontSize(settings.baseFontSize);
        applyEditorFontSize(settings.editorFontSize);
        // 字体加载失败不应阻塞初始化：回退到字体栈中的下一个字体即可。
        void loadConfiguredFonts(settings.fontFamily, settings.codeFontFamily).catch(
          () => undefined,
        );

        if (mounted) {
          setRequiresAuthentication(false);
          applyThemeSettings(settings);
          setIsReady(true);
        }
      } catch (initializationError) {
        if (mounted) {
          // Socket.IO retries transports and reconnects within this deadline.
          if (Date.now() - startTime >= INITIALIZATION_TIMEOUT_MS) {
            setError(getInitializationErrorMessage(initializationError));
            return;
          }
          // Retry after 500ms
          timer = setTimeout(initializeApp, 500);
        }
      }
    };

    initializeApp();

    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [applyThemeSettings]);

  useEffect(() => {
    const activeThemePreset = appearance === "dark" ? darkThemePreset : lightThemePreset;
    const palette = resolveThemePalette(activeThemePreset, themeConfig, appearance);
    const themeVariables = resolveThemeVariables(palette, appearance, activeThemePreset);
    applyThemePalette(palette, appearance, activeThemePreset);
    if (!hasLoadedPreferencesRef.current) return;
    publishDesktopAppearance({
      appearance,
      themeVariables,
      persist: true,
    });
  }, [appearance, darkThemePreset, lightThemePreset, themeConfig]);

  useEffect(() => {
    const publishLanguage = (language: string) => {
      if (language === "zh-CN" || language === "en")
        publishDesktopLanguage(language as LanguageCode);
    };

    publishLanguage(i18n.resolvedLanguage ?? i18n.language);
    i18n.on("languageChanged", publishLanguage);
    return () => i18n.off("languageChanged", publishLanguage);
  }, []);

  return (
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <>
          <Theme
            appearance={appearance}
            accentColor="gray"
            grayColor="gray"
            panelBackground="solid"
          >
            {!isReady ? (
              <GlobalLoading
                error={error}
                onRetry={() => window.location.reload()}
              />
            ) : requiresAuthentication ? (
              <AuthPage />
            ) : (
              <ErrorBoundary
                FallbackComponent={AppCrashFallback}
                onError={(err) => captureException(err, { source: "react-render" })}
              >
                <AppContent
                  appearance={appearance}
                  version={FRONTEND_VERSION}
                  themeMode={themeMode}
                  setThemeMode={applyThemeMode}
                  setThemeSettings={applyThemeSettings}
                  previewThemeSettings={previewThemeSettings}
                  toggleTheme={toggleTheme}
                />
              </ErrorBoundary>
            )}
          </Theme>
          {isReady && !requiresAuthentication ? <Toaster appearance={appearance} /> : null}
        </>
      </QueryClientProvider>
    </StrictMode>
  );
}

registerSW();

getOrCreateRoot(document.getElementById("root")!).render(<Root />);
