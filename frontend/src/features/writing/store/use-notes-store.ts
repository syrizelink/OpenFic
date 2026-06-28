import { create } from "zustand";
import { getPreference, setPreference } from "@/lib/local-db";

const EXPANDED_NOTE_CATEGORY_IDS_KEY = "writing.expandedNoteCategoryIds";

interface NotesStore {
  expandedNoteCategoryIds: Set<string>;
  currentNoteId: string | null;
  hasHydratedExpanded: boolean;

  toggleNoteCategoryExpanded: (id: string) => void;
  setNoteCategoryExpanded: (id: string, expanded: boolean) => void;
  setCurrentNote: (id: string | null) => void;
  hydrateExpandedNoteCategoryIds: () => Promise<void>;
}

export const useNotesStore = create<NotesStore>((set, get) => ({
  expandedNoteCategoryIds: new Set(),
  currentNoteId: null,
  hasHydratedExpanded: false,

  toggleNoteCategoryExpanded: (id) => {
    const isExpanded = get().expandedNoteCategoryIds.has(id);
    get().setNoteCategoryExpanded(id, !isExpanded);
  },

  setNoteCategoryExpanded: (id, expanded) => {
    const next = new Set(get().expandedNoteCategoryIds);
    if (expanded) {
      next.add(id);
    } else {
      next.delete(id);
    }
    set({ expandedNoteCategoryIds: next });
    void setPreference(EXPANDED_NOTE_CATEGORY_IDS_KEY, JSON.stringify([...next]));
  },

  setCurrentNote: (id) => set({ currentNoteId: id }),

  hydrateExpandedNoteCategoryIds: async () => {
    const rawValue = await getPreference(EXPANDED_NOTE_CATEGORY_IDS_KEY);
    if (!rawValue) {
      set({ hasHydratedExpanded: true });
      return;
    }

    try {
      const ids = JSON.parse(rawValue);
      if (!Array.isArray(ids)) {
        set({ hasHydratedExpanded: true });
        return;
      }
      set({
        expandedNoteCategoryIds: new Set(
          ids.filter((id): id is string => typeof id === "string" && id.length > 0)
        ),
        hasHydratedExpanded: true,
      });
    } catch {
      set({ hasHydratedExpanded: true });
    }
  },
}));
