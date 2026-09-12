/**
 * World Info Store
 *
 * Mengelola status UI halaman buku dunia memakai Zustand.
 */

import { create } from "zustand";

interface WorldInfoStoreState {
  /** ID proyek saat ini */
  currentProjectId: string | null;
  /** ID buku dunia yang sedang dipilih */
  currentWorldInfoId: string | null;
  /** ID entri yang sedang dipilih */
  currentEntryId: string | null;
  /** Kata kunci pencarian */
  searchQuery: string;
  /** Status terbuka bilah sisi pada peranti bergerak */
  sidebarOpen: boolean;
  /** Halaman asal (dipakai untuk navigasi kembali) */
  fromWriting: boolean;
  /** ID proyek asal */
  fromProjectId: string | null;

  // Status terkait pengurutan tarik-lepas
  /** Menandai mode tarik-lepas sedang aktif */
  isDragMode: boolean;
  /** Menandai ada perubahan tarik-lepas yang belum tersimpan */
  hasUnsavedDragChanges: boolean;
  /** Data sementara pengurutan tarik-lepas: ID entri -> urutan baru */
  dragOrderMap: Record<string, number>;
  /** Data urutan asli */
  originalOrder: Record<string, number>;
}

interface WorldInfoStoreActions {
  /** Menyetel proyek saat ini */
  setCurrentProject: (projectId: string | null) => void;
  /** Menyetel buku dunia saat ini */
  setCurrentWorldInfo: (worldInfoId: string | null) => void;
  /** Menyetel entri yang sedang dipilih */
  setCurrentEntry: (entryId: string | null) => void;
  /** Menyetel kata kunci pencarian */
  setSearchQuery: (query: string) => void;
  /** Menyetel status bilah sisi */
  setSidebarOpen: (open: boolean) => void;
  /** Menyetel informasi asal */
  setFromWriting: (fromWriting: boolean, projectId: string | null) => void;

  // Action terkait tarik-lepas
  /** Masuk ke mode tarik-lepas */
  enterDragMode: (entries: Array<{ id: string; order: number }>) => void;
  /** Keluar dari mode tarik-lepas */
  exitDragMode: () => void;
  /** Mengurutkan ulang entri */
  reorderEntries: (fromIndex: number, toIndex: number, entryIds: string[]) => void;
  /** Mengambil entri yang perlu diperbarui setelah tarik-lepas */
  getDragChanges: () => Array<{ id: string; newOrder: number }>;

  /** Mereset seluruh status */
  reset: () => void;
}

type WorldInfoStore = WorldInfoStoreState & WorldInfoStoreActions;

const initialState: WorldInfoStoreState = {
  currentProjectId: null,
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

  setCurrentProject: (projectId) => set({ currentProjectId: projectId, currentEntryId: null }),
  setCurrentWorldInfo: (worldInfoId) => set({ currentWorldInfoId: worldInfoId }),
  setCurrentEntry: (entryId) => set({ currentEntryId: entryId }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setFromWriting: (fromWriting, projectId) => set({ fromWriting, fromProjectId: projectId }),

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

    // Menghitung ulang urutan seluruh entri
    const reorderedIds = [...entryIds];
    const [movedId] = reorderedIds.splice(fromIndex, 1);
    reorderedIds.splice(toIndex, 0, movedId);

    reorderedIds.forEach((id, index) => {
      newMap[id] = index + 1;
    });

    // Memeriksa adanya perubahan yang belum tersimpan
    const hasChanges = Object.keys(newMap).some((key) => newMap[key] !== originalOrder[key]);

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
