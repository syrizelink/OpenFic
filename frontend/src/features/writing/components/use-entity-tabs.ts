import { useEffect, useState } from "react";

import type { EditorTab } from "../lib/tab.types";

export function useEntityTabs(
  projectId: string | null,
  selectedId: string | null,
  items: { id: string; name: string }[],
  isLoaded: boolean,
  select: (id: string | null) => void,
) {
  const [state, setState] = useState<{ projectId: string | null; tabs: EditorTab[] }>({
    projectId,
    tabs: [],
  });
  const tabs = state.projectId === projectId ? state.tabs : [];

  useEffect(() => {
    setState((previous) => {
      let next = previous.projectId === projectId ? previous.tabs : [];
      if (isLoaded) {
        next = next.filter((tab) => items.some((item) => item.id === tab.id));
        next = next.map((tab) => ({
          ...tab,
          title: items.find((item) => item.id === tab.id)?.name ?? tab.title,
        }));
      }
      const selected = items.find((item) => item.id === selectedId);
      if (selected && !next.some((tab) => tab.id === selected.id)) {
        next = [
          ...next,
          {
            id: selected.id,
            type: "note",
            refId: selected.id,
            title: selected.name,
            isLocked: false,
            scrollTop: 0,
          },
        ];
      }
      if (
        previous.projectId === projectId &&
        next.length === previous.tabs.length &&
        next.every(
          (tab, index) =>
            tab.id === previous.tabs[index].id &&
            tab.title === previous.tabs[index].title &&
            tab.isLocked === previous.tabs[index].isLocked,
        )
      )
        return previous;
      return { projectId, tabs: next };
    });
  }, [projectId, selectedId, items, isLoaded]);

  const update = (fn: (tabs: EditorTab[]) => EditorTab[]) =>
    setState((previous) => ({
      projectId,
      tabs: fn(previous.projectId === projectId ? previous.tabs : []),
    }));
  const closeTab = (id: string) => {
    const index = tabs.findIndex((tab) => tab.id === id);
    if (index < 0 || tabs[index].isLocked) return;
    const remaining = tabs.filter((tab) => tab.id !== id);
    update(() => remaining);
    if (selectedId === id) select(remaining[Math.min(index, remaining.length - 1)]?.id ?? null);
  };
  return {
    tabs,
    activeTabId: selectedId,
    setActiveTab: (id: string) => select(id),
    closeTab,
    closeOtherTabs: (id: string) => {
      update((current) => current.filter((tab) => tab.id === id || tab.isLocked));
      select(id);
    },
    closeAllTabs: () => {
      const remaining = tabs.filter((tab) => tab.isLocked);
      update(() => remaining);
      select(remaining[0]?.id ?? null);
    },
    toggleLock: (id: string) =>
      update((current) =>
        current.map((tab) => (tab.id === id ? { ...tab, isLocked: !tab.isLocked } : tab)),
      ),
    reorderTabs: (activeId: string, overId: string) =>
      update((current) => {
        const from = current.findIndex((tab) => tab.id === activeId);
        const to = current.findIndex((tab) => tab.id === overId);
        if (from < 0 || to < 0) return current;
        const next = [...current];
        next.splice(to, 0, next.splice(from, 1)[0]);
        return next;
      }),
  };
}
