/**
 * Projects Store
 *
 * 使用 Zustand 管理项目列表的本地 UI 状态。
 */

import { create } from "zustand";

/** 视图模式 */
export type ViewMode = "grid" | "list";

/** 排序方式 */
export type SortBy = "updated_at" | "created_at" | "title";

/** 排序方向 */
export type SortOrder = "asc" | "desc";

interface ProjectsStoreState {
  /** 视图模式 */
  viewMode: ViewMode;
  /** 搜索关键词 */
  searchQuery: string;
  /** 排序方式 */
  sortBy: SortBy;
  /** 排序方向 */
  sortOrder: SortOrder;
}

interface ProjectsStoreActions {
  /** 设置视图模式 */
  setViewMode: (mode: ViewMode) => void;
  /** 设置搜索关键词 */
  setSearchQuery: (query: string) => void;
  /** 设置排序方式 */
  setSortBy: (sortBy: SortBy) => void;
  /** 设置排序方向 */
  setSortOrder: (order: SortOrder) => void;
  /** 重置所有状态 */
  reset: () => void;
}

type ProjectsStore = ProjectsStoreState & ProjectsStoreActions;

const initialState: ProjectsStoreState = {
  viewMode: "grid",
  searchQuery: "",
  sortBy: "updated_at",
  sortOrder: "desc",
};

export const useProjectsStore = create<ProjectsStore>((set) => ({
  ...initialState,

  setViewMode: (mode) => set({ viewMode: mode }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSortBy: (sortBy) => set({ sortBy }),
  setSortOrder: (order) => set({ sortOrder: order }),
  reset: () => set(initialState),
}));
