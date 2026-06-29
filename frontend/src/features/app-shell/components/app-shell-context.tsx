import { createContext, useContext } from "react";

import type { SettingsDialogRoute } from "@/features/settings/lib/settings-route";

interface AppShellContextValue {
  isMobile: boolean;
  isSidebarOpen: boolean;
  isSettingsOpen: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  openSettings: (route?: SettingsDialogRoute) => void;
  closeSettings: () => void;
}

export const AppShellContext = createContext<AppShellContextValue | null>(null);

export function useAppShell(): AppShellContextValue {
  const context = useContext(AppShellContext);

  if (!context) {
    throw new Error("useAppShell must be used within AppLayout");
  }

  return context;
}
