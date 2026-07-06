/**
 * Prompt Chain Store - 提示词链状态管理
 *
 * 管理 Work Dir 等全局状态，并持久化到 IndexedDB。
 */

import { create } from "zustand";

import { getWorkDirSettings, saveWorkDirSettings } from "@/lib/local-db";

interface WorkDir {
  projectId: string | null;
  chapterId: string | null; // null 表示最新章节
}

interface PromptChainState {
  workDir: WorkDir;
  workDirLoaded: boolean;
  setWorkDir: (workDir: Partial<WorkDir>) => void;
  clearWorkDir: () => void;
  loadWorkDirFromDB: () => Promise<void>;
}

export const usePromptChainStore = create<PromptChainState>((set, get) => ({
  workDir: {
    projectId: null,
    chapterId: null,
  },
  workDirLoaded: false,

  setWorkDir: (updates) => {
    const newWorkDir = { ...get().workDir, ...updates };
    set({ workDir: newWorkDir });
    // 持久化到 IndexedDB
    saveWorkDirSettings(newWorkDir.projectId, newWorkDir.chapterId);
  },

  clearWorkDir: () => {
    set({ workDir: { projectId: null, chapterId: null } });
    saveWorkDirSettings(null, null);
  },

  loadWorkDirFromDB: async () => {
    const settings = await getWorkDirSettings();
    if (settings) {
      set({
        workDir: {
          projectId: settings.projectId,
          chapterId: settings.chapterId,
        },
        workDirLoaded: true,
      });
    } else {
      set({ workDirLoaded: true });
    }
  },
}));
