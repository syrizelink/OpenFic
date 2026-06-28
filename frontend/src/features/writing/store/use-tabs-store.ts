/**
 * Editor Tabs Store
 *
 * 编辑器标签页状态管理，使用 Zustand + Dexie (IndexedDB) 持久化。
 * 按项目 ID 隔离存储，切换项目时自动加载对应的标签页状态。
 */

import { create } from "zustand";
import type { EditorTab } from "../lib/tab.types";
import { MAX_TABS, isEmptyTab, generateEmptyTabId } from "../lib/tab.types";
import {
  getProjectTabs,
  setProjectTabs,
  type EditorTabRecord,
} from "@/lib/local-db";

interface TabsState {
  currentProjectId: string | null;
  tabs: EditorTab[];
  activeTabId: string | null;
  isLoaded: boolean;
}

interface TabsActions {
  setCurrentProject: (projectId: string) => Promise<void>;
  openTab: (refId: string, title: string, type?: "chapter" | "note") => void;
  openSingleTab: (refId: string, title: string, type?: "chapter" | "note") => void;
  closeTab: (tabId: string) => void;
  closeOtherTabs: (tabId: string) => void;
  closeAllTabs: () => void;
  setActiveTab: (tabId: string | null) => void;
  toggleLock: (tabId: string) => void;
  updateTabTitle: (tabId: string, title: string) => void;
  syncTabsWithChapters: (chapters: { id: string; title: string }[]) => void;
  syncTabs: (items: { id: string; title: string }[], type: "chapter" | "note") => void;
  showEmptyTab: () => void;
  reorderTabs: (activeId: string, overId: string) => void;
}

type TabsStore = TabsState & TabsActions;

function toRecord(tab: EditorTab): EditorTabRecord {
  return {
    id: tab.id,
    refId: tab.refId,
    type: tab.type,
    title: tab.title,
    isLocked: tab.isLocked,
  };
}

function fromRecord(record: EditorTabRecord): EditorTab {
  const type = (record.type as "chapter" | "note") || "chapter";
  const refId = record.refId ?? record.chapterId ?? null;
  return {
    id: record.id,
    type,
    refId,
    title: record.title,
    isLocked: record.isLocked,
  };
}

async function persistTabs(
  projectId: string | null,
  tabs: EditorTab[],
  activeTabId: string | null
): Promise<void> {
  if (!projectId) return;
  await setProjectTabs(projectId, tabs.map(toRecord), activeTabId);
}

export const useTabsStore = create<TabsStore>()((set, get) => ({
  currentProjectId: null,
  tabs: [],
  activeTabId: null,
  isLoaded: false,

  setCurrentProject: async (projectId) => {
    const state = get();

    if (state.currentProjectId === projectId && state.isLoaded) return;

    if (state.currentProjectId !== projectId) {
      set({
        currentProjectId: projectId,
        tabs: [],
        activeTabId: null,
        isLoaded: false,
      });
    }

    const saved = await getProjectTabs(projectId);
    if (saved) {
      set({
        currentProjectId: projectId,
        tabs: saved.tabs.map(fromRecord),
        activeTabId: saved.activeTabId,
        isLoaded: true,
      });
    } else {
      set({
        currentProjectId: projectId,
        tabs: [],
        activeTabId: null,
        isLoaded: true,
      });
    }
  },

  openTab: (refId, title, type = "chapter") => {
    const { tabs, currentProjectId } = get();

    const existingTab = tabs.find((t) => t.refId === refId && t.type === type);
    if (existingTab) {
      set({ activeTabId: existingTab.id });
      persistTabs(currentProjectId, tabs, existingTab.id);
      return;
    }

    const nonEmptyTabs = tabs.filter((t) => !isEmptyTab(t.id));
    let newTabs = [...tabs];

    if (nonEmptyTabs.length >= MAX_TABS) {
      const unlockIndex = nonEmptyTabs.findIndex((t) => !t.isLocked);
      if (unlockIndex === -1) {
        return;
      }
      const tabToRemove = nonEmptyTabs[unlockIndex];
      newTabs = tabs.filter((t) => t.id !== tabToRemove.id);
    }

    const newTab: EditorTab = {
      id: `${type}:${refId}`,
      type,
      refId,
      title,
      isLocked: false,
    };
    newTabs.push(newTab);

    set({
      tabs: newTabs,
      activeTabId: newTab.id,
    });
    persistTabs(currentProjectId, newTabs, newTab.id);
  },

  openSingleTab: (refId, title, type = "chapter") => {
    const { currentProjectId } = get();
    const newTab: EditorTab = {
      id: `${type}:${refId}`,
      type,
      refId,
      title,
      isLocked: false,
    };

    set({
      tabs: [newTab],
      activeTabId: newTab.id,
    });
    persistTabs(currentProjectId, [newTab], newTab.id);
  },

  closeTab: (tabId) => {
    const { tabs, activeTabId, currentProjectId } = get();
    const tabToClose = tabs.find((t) => t.id === tabId);

    if (!tabToClose || tabToClose.isLocked) {
      return;
    }

    const tabIndex = tabs.findIndex((t) => t.id === tabId);
    const newTabs = tabs.filter((t) => t.id !== tabId);

    if (newTabs.length === 0) {
      const emptyTabId = generateEmptyTabId();
      const emptyTab: EditorTab = {
        id: emptyTabId,
        type: "chapter",
        refId: null,
        title: "",
        isLocked: false,
      };
      set({
        tabs: [emptyTab],
        activeTabId: emptyTabId,
      });
      persistTabs(currentProjectId, [emptyTab], emptyTabId);
      return;
    }

    let newActiveId = activeTabId;
    if (activeTabId === tabId) {
      if (tabIndex >= newTabs.length) {
        newActiveId = newTabs[newTabs.length - 1].id;
      } else {
        newActiveId = newTabs[tabIndex].id;
      }
    }

    set({
      tabs: newTabs,
      activeTabId: newActiveId,
    });
    persistTabs(currentProjectId, newTabs, newActiveId);
  },

  closeOtherTabs: (tabId) => {
    const { tabs, currentProjectId } = get();
    const newTabs = tabs.filter((t) => t.id === tabId || t.isLocked);
    set({
      tabs: newTabs,
      activeTabId: tabId,
    });
    persistTabs(currentProjectId, newTabs, tabId);
  },

  closeAllTabs: () => {
    const { tabs, currentProjectId } = get();
    const lockedTabs = tabs.filter((t) => t.isLocked && !isEmptyTab(t.id));

    if (lockedTabs.length === 0) {
      const emptyTabId = generateEmptyTabId();
      const emptyTab: EditorTab = {
        id: emptyTabId,
        type: "chapter",
        refId: null,
        title: "",
        isLocked: false,
      };
      set({
        tabs: [emptyTab],
        activeTabId: emptyTabId,
      });
      persistTabs(currentProjectId, [emptyTab], emptyTabId);
    } else {
      set({
        tabs: lockedTabs,
        activeTabId: lockedTabs[0].id,
      });
      persistTabs(currentProjectId, lockedTabs, lockedTabs[0].id);
    }
  },

  setActiveTab: (tabId) => {
    const { tabs, currentProjectId } = get();
    set({ activeTabId: tabId });
    persistTabs(currentProjectId, tabs, tabId);
  },

  showEmptyTab: () => {
    const { tabs, currentProjectId } = get();

    const emptyTabId = generateEmptyTabId();
    const emptyTab: EditorTab = {
      id: emptyTabId,
      type: "chapter",
      refId: null,
      title: "",
      isLocked: false,
    };

    const newTabs = [...tabs, emptyTab];
    set({
      tabs: newTabs,
      activeTabId: emptyTabId,
    });
    persistTabs(currentProjectId, newTabs, emptyTabId);
  },

  toggleLock: (tabId) => {
    const { tabs, activeTabId, currentProjectId } = get();
    const newTabs = tabs.map((t) =>
      t.id === tabId ? { ...t, isLocked: !t.isLocked } : t
    );
    set({ tabs: newTabs });
    persistTabs(currentProjectId, newTabs, activeTabId);
  },

  updateTabTitle: (tabId, title) => {
    const { tabs, activeTabId, currentProjectId } = get();
    const newTabs = tabs.map((t) => (t.id === tabId ? { ...t, title } : t));
    set({ tabs: newTabs });
    persistTabs(currentProjectId, newTabs, activeTabId);
  },

  syncTabsWithChapters: (chapters) => {
    get().syncTabs(chapters, "chapter");
  },

  syncTabs: (items, type) => {
    const { tabs, activeTabId, currentProjectId } = get();
    const titleMap = new Map(items.map((item) => [item.id, item.title]));
    const newTabs = tabs.flatMap((tab) => {
      if (isEmptyTab(tab.id) || !tab.refId) return [tab];
      if (tab.type !== type) return [tab];

      const latestTitle = titleMap.get(tab.refId);
      if (latestTitle === undefined) return [];
      if (tab.title === latestTitle) return [tab];

      return [{ ...tab, title: latestTitle }];
    });

    let newActiveId = activeTabId;
    if (
      activeTabId &&
      !isEmptyTab(activeTabId)
    ) {
      const activeTab = tabs.find((t) => t.id === activeTabId);
      if (activeTab?.type === type && activeTab.refId && !titleMap.has(activeTab.refId)) {
        newActiveId = newTabs.length > 0 ? newTabs[0].id : null;
      }
    }

    const hasTabChanges =
      newTabs.length !== tabs.length ||
      newTabs.some((tab, index) => tab.title !== tabs[index]?.title);

    if (hasTabChanges || newActiveId !== activeTabId) {
      set({
        tabs: newTabs,
        activeTabId: newActiveId,
      });
      persistTabs(currentProjectId, newTabs, newActiveId);
    }
  },

  reorderTabs: (activeId, overId) => {
    const { tabs, activeTabId, currentProjectId } = get();
    const oldIndex = tabs.findIndex((t) => t.id === activeId);
    const newIndex = tabs.findIndex((t) => t.id === overId);

    if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) {
      return;
    }

    const newTabs = [...tabs];
    const [removed] = newTabs.splice(oldIndex, 1);
    newTabs.splice(newIndex, 0, removed);

    set({ tabs: newTabs });
    persistTabs(currentProjectId, newTabs, activeTabId);
  },
}));

export const useActiveTabId = () => useTabsStore((s) => s.activeTabId);
export const useTabs = () => useTabsStore((s) => s.tabs);
export const useTabsLoaded = () => useTabsStore((s) => s.isLoaded);
