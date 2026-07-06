import { useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router";

import { SettingsDialog } from "@/features/settings";
import type { SettingsDialogRoute } from "@/features/settings/lib/settings-route";

import { AppShellContext } from "./app-shell-context";
import { AppSidebar } from "./app-sidebar";
import "./app-layout.css";
import { StatusBar } from "./status-bar";

interface AppLayoutProps {
  appearance: "light" | "dark";
  version: string;
  onAppearanceChange: (appearance: "light" | "dark") => void;
  onToggleTheme: () => void;
}

export function AppLayout({ appearance, version, onAppearanceChange, onToggleTheme }: AppLayoutProps) {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsRoute, setSettingsRoute] = useState<SettingsDialogRoute | undefined>(undefined);

  useEffect(() => {
    function handleResize() {
      const nextIsMobile = window.innerWidth < 768;
      setIsMobile(nextIsMobile);

      if (!nextIsMobile) {
        setIsSidebarOpen(false);
      }
    }

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const contextValue = useMemo(
    () => ({
      isMobile,
      isSidebarOpen,
      isSettingsOpen,
      openSidebar: () => setIsSidebarOpen(true),
      closeSidebar: () => setIsSidebarOpen(false),
      toggleSidebar: () => setIsSidebarOpen((prev) => !prev),
      openSettings: (route?: SettingsDialogRoute) => {
        setSettingsRoute(route);
        setIsSettingsOpen(true);
      },
      closeSettings: () => setIsSettingsOpen(false),
    }),
    [isMobile, isSidebarOpen, isSettingsOpen],
  );

  return (
    <AppShellContext.Provider value={contextValue}>
      <div className="app-layout-root">
        <div className="app-layout-body">
          <AppSidebar
            appearance={appearance}
            onToggleTheme={onToggleTheme}
          />

          <div className="app-layout-content">
            <Outlet />
          </div>
        </div>

        <StatusBar version={version} />

        <SettingsDialog
          appearance={appearance}
          onAppearanceChange={onAppearanceChange}
          open={isSettingsOpen}
          onOpenChange={setIsSettingsOpen}
          route={settingsRoute}
        />
      </div>
    </AppShellContext.Provider>
  );
}
