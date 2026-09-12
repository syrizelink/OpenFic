/**
 * Projects Store
 *
 * Mengelola status UI lokal daftar proyek memakai Zustand.
 */

import { create } from "zustand";

/** Mode tampilan */
export type ViewMode = "grid" | "list";

/** Cara pengurutan */
export type SortBy = "updated_at" | "created_at" | "title";

/** Arah pengurutan */
export type SortOrder = "asc" | "desc";

interface ProjectsStoreState {
  /** Mode tampilan */
  viewMode: ViewMode;
  /** Kata kunci pencarian */
  searchQuery: string;
  /** Cara pengurutan */
  sortBy: SortBy;
  /** Arah pengurutan */
  sortOrder: SortOrder;
}

interface ProjectsStoreActions {
  /** Menyetel mode tampilan */
  setViewMode: (mode: ViewMode) => void;
  /** Menyetel kata kunci pencarian */
  setSearchQuery: (query: string) => void;
  /** Menyetel cara pengurutan */
  setSortBy: (sortBy: SortBy) => void;
  /** Menyetel arah pengurutan */
  setSortOrder: (order: SortOrder) => void;
  /** Mereset seluruh status */
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
