import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense, useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router";

import App from "./App.tsx";
import { GlobalLoading } from "./components";
import { Toaster } from "./components/toaster";
import { AppLayout } from "./features/app-shell";
import { CharactersPage } from "./features/characters";
import { PromptChainsPage } from "./features/prompt-chains";
import { fetchSettings } from "./features/settings/lib/settings-api";
import type { Settings, ThemeMode } from "./features/settings/lib/settings.types";
import { WorldInfoPage } from "./features/world-info";
import { WritingPage } from "./features/writing";
import { checkHealth } from "./lib/api-client";
import { publishDesktopAppearance } from "./lib/desktop-appearance-bridge";
import { applyCodeFontFamily, applyFontFamily, loadConfiguredFonts } from "./lib/font-utils";
import { getOrCreateRoot } from "./lib/get-or-create-root";
import { loadRuntimeConfig } from "./lib/runtime-config";
import { connectSocket } from "./lib/socket-client";
import { preloadTiktokenEncoding } from "./lib/tiktoken-utils";
import { registerSW } from "./pwa/register-sw";

import "streamdown/styles.css";
import "./styles/index.css";

// 初始化 i18n
import "./i18n";

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

const DashboardPage = lazy(() =>
  import("./features/dashboard/pages/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  })),
);

function AppContent({
  appearance,
  themeMode,
  version,
  setThemeMode,
  toggleTheme,
}: {
  appearance: "light" | "dark";
  themeMode: ThemeMode;
  version: string;
  setThemeMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}) {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <AppLayout
              appearance={appearance}
              themeMode={themeMode}
              version={version}
              onThemeModeChange={setThemeMode}
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

function useSystemPrefersDark(): boolean {
  const [prefersDark, setPrefersDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (event: MediaQueryListEvent) => {
      setPrefersDark(event.matches);
    };
    mq.addEventListener("change", handler);
    // Sync on mount in case the initial lazy value is stale
    setPrefersDark(mq.matches);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return prefersDark;
}

const THEME_CYCLE: ThemeMode[] = ["light", "dark", "system"];

function resolveAppearance(themeMode: ThemeMode, systemPrefersDark: boolean): "light" | "dark" {
  if (themeMode === "system") {
    return systemPrefersDark ? "dark" : "light";
  }
  return themeMode;
}

function Root() {
  const [themeMode, setThemeMode] = useState<ThemeMode>("light");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState(false);
  const systemPrefersDark = useSystemPrefersDark();
  const appearance = resolveAppearance(themeMode, systemPrefersDark);

  const toggleTheme = () => {
    setThemeMode((prev) => {
      const idx = THEME_CYCLE.indexOf(prev);
      return THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
    });
  };

  useEffect(() => {
    let mounted = true;
    let timer: ReturnType<typeof setTimeout>;
    const startTime = Date.now();

    const initializeApp = async () => {
      try {
        await loadRuntimeConfig();

        const [, settings] = await Promise.all([
          checkHealth(),
          queryClient.fetchQuery({
            queryKey: ["settings"],
            queryFn: fetchSettings,
          }),
          preloadTiktokenEncoding(),
          connectSocket(),
        ]);

        applyFontFamily(settings.fontFamily);
        applyCodeFontFamily(settings.codeFontFamily);
        await loadConfiguredFonts(settings.fontFamily, settings.codeFontFamily);

        if (mounted) {
          setSettings(settings);
          setThemeMode((settings.theme as ThemeMode) ?? "light");
          setIsReady(true);
        }
      } catch {
        if (mounted) {
          // Check for timeout (30s)
          if (Date.now() - startTime > 30000) {
            setError(true);
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
  }, []);

  useEffect(() => {
    publishDesktopAppearance({
      appearance,
      fontFamily: settings?.fontFamily,
      codeFontFamily: settings?.codeFontFamily,
    });
  }, [appearance, settings?.fontFamily, settings?.codeFontFamily]);

  return (
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <>
          <Theme
            appearance={appearance}
            accentColor="gray"
            grayColor="gray"
            radius="medium"
            scaling="100%"
          >
            {!isReady ? (
              <GlobalLoading
                error={error}
                onRetry={() => window.location.reload()}
              />
            ) : (
              <AppContent
                appearance={appearance}
                themeMode={themeMode}
                version={FRONTEND_VERSION}
                setThemeMode={setThemeMode}
                toggleTheme={toggleTheme}
              />
            )}
          </Theme>
          {isReady ? <Toaster appearance={appearance} /> : null}
        </>
      </QueryClientProvider>
    </StrictMode>
  );
}

registerSW();

getOrCreateRoot(document.getElementById("root")!).render(<Root />);
