import { createContext, useContext } from "react";

import type { SettingsDialogRoute } from "@/features/settings/lib/settings-route";

import type { AssistantSidebarHostRegistration } from "./assistant-sidebar-host-state";

interface AppShellContextValue {
  isMobile: boolean;
  isSidebarOpen: boolean;
  isSettingsOpen: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  openSettings: (route?: SettingsDialogRoute) => void;
  closeSettings: () => void;
  appendToAssistant: (markup: string) => void;
  isAssistantSidebarOpen: boolean;
  openAssistantSidebar: () => void;
  closeAssistantSidebar: () => void;
  registerAssistantSidebarHost: (registration: AssistantSidebarHostRegistration) => void;
  clearAssistantSidebarHost: (id: string) => void;
}

export const AppShellContext = createContext<AppShellContextValue | null>(null);

export function useAppShell(): AppShellContextValue {
  const context = useContext(AppShellContext);

  if (!context) {
    throw new Error("useAppShell must be used within AppLayout");
  }

  return context;
}
