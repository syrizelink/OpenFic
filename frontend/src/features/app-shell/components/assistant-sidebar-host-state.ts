import type { AssistantSidebarState } from "@/features/assistant/lib/assistant-state.types";

export interface AssistantSidebarHostRegistration {
  id: string;
  host: HTMLElement | null;
  projectId: string;
  isMobileOverlay: boolean;
  isOpen: boolean;
  onStateChange?: (state: AssistantSidebarState) => void;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  onClose?: () => void;
}

export interface AssistantSidebarHostState extends AssistantSidebarHostRegistration {
  isActive: boolean;
}

export function registerAssistantSidebarHost(
  current: AssistantSidebarHostState | null,
  registration: AssistantSidebarHostRegistration,
): AssistantSidebarHostState {
  if (
    current &&
    current.id === registration.id &&
    current.host === registration.host &&
    current.projectId === registration.projectId &&
    current.isMobileOverlay === registration.isMobileOverlay &&
    current.isOpen === registration.isOpen &&
    current.onStateChange === registration.onStateChange &&
    current.onOpenMentionChapter === registration.onOpenMentionChapter &&
    current.onClose === registration.onClose
  ) {
    return current;
  }
  return { ...registration, isActive: true };
}

export function clearAssistantSidebarHost(
  current: AssistantSidebarHostState | null,
  id: string,
): AssistantSidebarHostState | null {
  if (!current || current.id !== id) return current;
  return { ...current, host: null, isActive: false };
}
