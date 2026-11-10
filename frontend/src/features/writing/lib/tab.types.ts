export interface EditorTab {
  id: string;
  type: "chapter" | "note";
  refId: string | null;
  title: string;
  isLocked: boolean;
  scrollTop: number;
}

export const MAX_TABS = 10;
