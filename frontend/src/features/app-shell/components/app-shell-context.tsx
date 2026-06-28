import { createContext, useContext } from "react";

interface AppShellContextValue {
  isMobile: boolean;
  isSidebarOpen: boolean;
  isSettingsOpen: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  openSettings: () => void;
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
