/**
 * World Info Store
 *
 * 使用 Zustand 管理世界书页面的 UI 状态。
 */

import { create } from "zustand";

interface WorldInfoStoreState {
  /** 当前选中的世界书 ID */
  currentWorldInfoId: string | null;
  /** 当前选中的条目 ID */
  currentEntryId: string | null;
  /** 搜索关键词 */
  searchQuery: string;
  /** 移动端侧边栏是否打开 */
  sidebarOpen: boolean;
  /** 来源页面（用于返回导航） */
  fromWriting: boolean;
  /** 来源项目 ID */
  fromProjectId: string | null;

  // 拖拽排序相关状态
  /** 是否处于拖拽模式 */
  isDragMode: boolean;
  /** 是否有未保存的拖拽修改 */
  hasUnsavedDragChanges: boolean;
  /** 拖拽排序临时数据：条目ID -> 新排序 */
  dragOrderMap: Record<string, number>;
  /** 原始排序数据 */
  originalOrder: Record<string, number>;
}

interface WorldInfoStoreActions {
  /** 设置当前世界书 */
  setCurrentWorldInfo: (worldInfoId: string | null) => void;
  /** 设置当前选中的条目 */
  setCurrentEntry: (entryId: string | null) => void;
  /** 设置搜索关键词 */
  setSearchQuery: (query: string) => void;
  /** 设置侧边栏状态 */
  setSidebarOpen: (open: boolean) => void;
  /** 设置来源信息 */
  setFromWriting: (fromWriting: boolean, projectId: string | null) => void;

  // 拖拽相关 actions
  /** 进入拖拽模式 */
  enterDragMode: (entries: Array<{ id: string; order: number }>) => void;
  /** 退出拖拽模式 */
  exitDragMode: () => void;
  /** 重新排序条目 */
  reorderEntries: (
    fromIndex: number,
    toIndex: number,
    entryIds: string[]
  ) => void;
  /** 获取拖拽后需要更新的条目 */
  getDragChanges: () => Array<{ id: string; newOrder: number }>;

  /** 重置所有状态 */
  reset: () => void;
}

type WorldInfoStore = WorldInfoStoreState & WorldInfoStoreActions;

const initialState: WorldInfoStoreState = {
  currentWorldInfoId: null,
  currentEntryId: null,
  searchQuery: "",
  sidebarOpen: false,
  fromWriting: false,
  fromProjectId: null,
  isDragMode: false,
  hasUnsavedDragChanges: false,
  dragOrderMap: {},
  originalOrder: {},
};

export const useWorldInfoStore = create<WorldInfoStore>((set, get) => ({
  ...initialState,

  setCurrentWorldInfo: (worldInfoId) =>
    set({ currentWorldInfoId: worldInfoId }),
  setCurrentEntry: (entryId) => set({ currentEntryId: entryId }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setFromWriting: (fromWriting, projectId) =>
    set({ fromWriting, fromProjectId: projectId }),

  enterDragMode: (entries) => {
    const orderMap: Record<string, number> = {};
    entries.forEach((e) => {
      orderMap[e.id] = e.order;
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

  reorderEntries: (fromIndex, toIndex, entryIds) => {
    const { dragOrderMap, originalOrder } = get();
    const newMap = { ...dragOrderMap };

    // 重新计算所有条目的顺序
    const reorderedIds = [...entryIds];
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

  getDragChanges: () => {
    const { dragOrderMap, originalOrder } = get();
    const changes: Array<{ id: string; newOrder: number }> = [];

    Object.keys(dragOrderMap).forEach((id) => {
      if (dragOrderMap[id] !== originalOrder[id]) {
        changes.push({ id, newOrder: dragOrderMap[id] });
      }
    });

    return changes;
  },

  reset: () => set(initialState),
}));
