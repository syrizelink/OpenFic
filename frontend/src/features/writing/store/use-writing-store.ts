/**
 * Writing Store
 *
 * 写作状态管理，包含当前章节、拖拽排序、侧边栏状态等。
 */

import { create } from "zustand";
import { getPreference, setPreference } from "@/lib/local-db";

const EXPANDED_VOLUME_IDS_KEY = "writing.expandedVolumeIds";
const SIDEBAR_VIEW_KEY = "writing.sidebarView";

interface WritingStore {
  // 当前状态
  currentChapterId: string | null;
  isDragMode: boolean;
  hasUnsavedDragChanges: boolean;
  sidebarOpen: boolean;
  expandedVolumeIds: Set<string>;
  hasHydratedExpandedVolumeIds: boolean;
  hasStoredExpandedVolumeIdsPreference: boolean;
  sidebarView: "chapters" | "notes";

  // 拖拽排序临时数据：章节ID -> 新排序
  dragOrderMap: Record<string, number>;
  originalOrder: Record<string, number>;

  // Actions
  setCurrentChapter: (id: string | null) => void;
  enterDragMode: (chapters: Array<{ id: string; order: number }>) => void;
  exitDragMode: () => void;
  setDragOrder: (id: string, order: number) => void;
  reorderChapters: (
    fromIndex: number,
    toIndex: number,
    chapterIds: string[]
  ) => void;
  resetDragChanges: () => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  hydrateExpandedVolumeIds: () => Promise<void>;
  setVolumeExpanded: (volumeId: string, expanded: boolean) => void;
  toggleVolumeExpanded: (volumeId: string) => void;
  setSidebarView: (view: "chapters" | "notes") => void;
  hydrateSidebarView: () => Promise<void>;
}

export const useWritingStore = create<WritingStore>((set, get) => ({
  currentChapterId: null,
  isDragMode: false,
  hasUnsavedDragChanges: false,
  sidebarOpen: false,
  expandedVolumeIds: new Set(),
  hasHydratedExpandedVolumeIds: false,
  hasStoredExpandedVolumeIdsPreference: false,
  sidebarView: "chapters",
  dragOrderMap: {},
  originalOrder: {},

  setCurrentChapter: (id) => set({ currentChapterId: id }),

  enterDragMode: (chapters) => {
    const orderMap: Record<string, number> = {};
    chapters.forEach((c) => {
      orderMap[c.id] = c.order;
    });
    set({
      isDragMode: true,
      hasUnsavedDragChanges: false,
      dragOrderMap: { ...orderMap },
      originalOrder: { ...orderMap },
    });
  },

  exitDragMode: () =>
    set({
      isDragMode: false,
      hasUnsavedDragChanges: false,
      dragOrderMap: {},
      originalOrder: {},
    }),

  setDragOrder: (id, order) => {
    const { dragOrderMap, originalOrder } = get();
    const newMap = { ...dragOrderMap, [id]: order };

    // 检查是否有未保存的修改
    const hasChanges = Object.keys(newMap).some(
      (key) => newMap[key] !== originalOrder[key]
    );

    set({
      dragOrderMap: newMap,
      hasUnsavedDragChanges: hasChanges,
    });
  },

  reorderChapters: (fromIndex, toIndex, chapterIds) => {
    const { dragOrderMap, originalOrder } = get();
    const newMap = { ...dragOrderMap };

    // 重新计算所有章节的顺序
    const reorderedIds = [...chapterIds];
    const [movedId] = reorderedIds.splice(fromIndex, 1);
    reorderedIds.splice(toIndex, 0, movedId);

    reorderedIds.forEach((id, index) => {
      newMap[id] = index + 1;
    });

    // 检查是否有未保存的修改
    const hasChanges = Object.keys(newMap).some(
      (key) => newMap[key] !== originalOrder[key]
    );

    set({
      dragOrderMap: newMap,
      hasUnsavedDragChanges: hasChanges,
    });
  },

  resetDragChanges: () => {
    const { originalOrder } = get();
    set({
      dragOrderMap: { ...originalOrder },
      hasUnsavedDragChanges: false,
    });
  },

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  hydrateExpandedVolumeIds: async () => {
    const rawValue = await getPreference(EXPANDED_VOLUME_IDS_KEY);
    if (!rawValue) {
      set({ hasHydratedExpandedVolumeIds: true });
      return;
    }

    try {
      const ids = JSON.parse(rawValue);
      if (!Array.isArray(ids)) {
        set({ hasHydratedExpandedVolumeIds: true });
        return;
      }
      set({
        expandedVolumeIds: new Set(
          ids.filter((id): id is string => typeof id === "string" && id.length > 0)
        ),
        hasHydratedExpandedVolumeIds: true,
        hasStoredExpandedVolumeIdsPreference: true,
      });
    } catch {
      set({ hasHydratedExpandedVolumeIds: true });
    }
  },

  setVolumeExpanded: (volumeId, expanded) => {
    const next = new Set(get().expandedVolumeIds);
    if (expanded) {
      next.add(volumeId);
    } else {
      next.delete(volumeId);
    }
    set({ expandedVolumeIds: next });
    void setPreference(EXPANDED_VOLUME_IDS_KEY, JSON.stringify([...next]));
  },

  toggleVolumeExpanded: (volumeId) => {
    const isExpanded = get().expandedVolumeIds.has(volumeId);
    get().setVolumeExpanded(volumeId, !isExpanded);
  },

  setSidebarView: (view) => {
    set({ sidebarView: view });
    void setPreference(SIDEBAR_VIEW_KEY, view);
  },

  hydrateSidebarView: async () => {
    const rawValue = await getPreference(SIDEBAR_VIEW_KEY);
    if (rawValue === "notes") {
      set({ sidebarView: "notes" });
    }
  },
}));
