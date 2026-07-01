import { lazy, StrictMode, Suspense, useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router";
import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App.tsx";
import { AppLayout } from "./features/app-shell";
import { WritingPage } from "./features/writing";
import { WorldInfoPage } from "./features/world-info";
import { PromptChainsPage } from "./features/prompt-chains";
import { getOrCreateRoot } from "./lib/get-or-create-root";
import { fetchSettings } from "./features/settings/lib/settings-api";
import {
  applyCodeFontFamily,
  applyFontFamily,
  loadConfiguredFonts,
} from "./lib/font-utils";
import { Toaster } from "./components/toaster";
import { GlobalLoading } from "./components";
import { checkHealth } from "./lib/api-client";
import { loadRuntimeConfig } from "./lib/runtime-config";
import { preloadTiktokenEncoding } from "./lib/tiktoken-utils";
import { publishDesktopAppearance } from "./lib/desktop-appearance-bridge";
import type { Settings } from "./features/settings/lib/settings.types";
import "streamdown/styles.css";
import "./styles/index.css";

// 初始化 i18n
import "./i18n";

/* eslint-disable react-refresh/only-export-components */
// 创建 QueryClient 实例（保持在组件外部以避免重新创建）
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 分钟
      retry: 1,
    },
  },
});

const DashboardPage = lazy(() =>
  import("./features/dashboard/pages/dashboard-page").then((module) => ({ default: module.DashboardPage }))
);

function AppContent({
  appearance,
  setAppearance,
  toggleTheme,
}: {
  appearance: "light" | "dark";
  setAppearance: (appearance: "light" | "dark") => void;
  toggleTheme: () => void;
}) {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <AppLayout appearance={appearance} onAppearanceChange={setAppearance} onToggleTheme={toggleTheme} />
          }
        >
          <Route path="/" element={<App />} />
          <Route path="/projects/:projectId" element={<WritingPage />} />
          <Route path="/world-info" element={<WorldInfoPage />} />
          <Route path="/prompt-chains" element={<PromptChainsPage />} />
          <Route
            path="/dashboard"
            element={
              <Suspense fallback={null}>
                <DashboardPage appearance={appearance} />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function Root() {
  const [appearance, setAppearance] = useState<"light" | "dark">("light");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState(false);

  const toggleTheme = () => {
    setAppearance((prev) => (prev === "light" ? "dark" : "light"));
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
        ]);

        applyFontFamily(settings.fontFamily);
        applyCodeFontFamily(settings.codeFontFamily);
        await loadConfiguredFonts(settings.fontFamily, settings.codeFontFamily);

        if (mounted) {
          setSettings(settings);
          setAppearance(settings.theme);
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
              <AppContent appearance={appearance} setAppearance={setAppearance} toggleTheme={toggleTheme} />
            )}
          </Theme>
          {isReady ? <Toaster appearance={appearance} /> : null}
        </>
      </QueryClientProvider>
    </StrictMode>
  );
}

getOrCreateRoot(document.getElementById("root")!).render(<Root />);
