export interface EditorTab {
  id: string;
  type: "chapter" | "note";
  refId: string | null;
  title: string;
  isLocked: boolean;
}

export const MAX_TABS = 10;

export const EMPTY_TAB_PREFIX = "__empty__";

export function isEmptyTab(tabId: string): boolean {
  return tabId.startsWith(EMPTY_TAB_PREFIX);
}

export function generateEmptyTabId(): string {
  return `${EMPTY_TAB_PREFIX}${Date.now()}`;
}
