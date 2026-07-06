import { Box } from "@radix-ui/themes";
import { useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router";

import { SettingsDialog } from "@/features/settings";
import type { SettingsDialogRoute } from "@/features/settings/lib/settings-route";

import { AppShellContext } from "./app-shell-context";
import { AppSidebar } from "./app-sidebar";

interface AppLayoutProps {
  appearance: "light" | "dark";
  onAppearanceChange: (appearance: "light" | "dark") => void;
  onToggleTheme: () => void;
}

export function AppLayout({ appearance, onAppearanceChange, onToggleTheme }: AppLayoutProps) {
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
      <Box
        style={{
          height: "100dvh",
          overflow: "hidden",
        }}
      >
        <AppSidebar
          appearance={appearance}
          onToggleTheme={onToggleTheme}
        />

        <Box
          style={{
            paddingLeft: "var(--app-sidebar-width)",
            height: "100%",
            overflow: "hidden",
            transition: "padding-left 0.24s cubic-bezier(0.22, 1, 0.36, 1)",
          }}
        >
          <Outlet />
        </Box>

        <SettingsDialog
          appearance={appearance}
          onAppearanceChange={onAppearanceChange}
          open={isSettingsOpen}
          onOpenChange={setIsSettingsOpen}
          route={settingsRoute}
        />
      </Box>
    </AppShellContext.Provider>
  );
}
