import { useEffect, useRef, useState } from "react";

import { getPreference, setPreference } from "@/lib/local-db";

import type { EditorTab } from "../lib/tab.types";

const EMPTY_TABS: EditorTab[] = [];

export function useEntityTabs(
  kind: "characters" | "world-info",
  projectId: string | null,
  selectedId: string | null,
  items: { id: string; name: string }[],
  isLoaded: boolean,
  select: (id: string | null) => void,
) {
  const [state, setState] = useState<{
    projectId: string | null;
    tabs: EditorTab[];
    isLoaded: boolean;
    hasSaved: boolean;
  }>({
    projectId,
    tabs: [],
    isLoaded: false,
    hasSaved: false,
  });
  const selectRef = useRef(select);
  selectRef.current = select;
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const tabs = state.projectId === projectId ? state.tabs : EMPTY_TABS;
  const isHydrated = state.projectId === projectId && state.isLoaded;

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    const initialSelection = selectedIdRef.current;
    void getPreference(`editor-tabs.${kind}.${projectId}`).then((value) => {
      if (cancelled) return;
      let saved: { tabs: EditorTab[]; activeTabId: string | null } | null = null;
      try {
        const parsed = value ? JSON.parse(value) : null;
        if (parsed && Array.isArray(parsed.tabs)) {
          saved = {
            tabs: parsed.tabs.filter(
              (tab: EditorTab) => typeof tab?.id === "string" && typeof tab.title === "string",
            ),
            activeTabId: typeof parsed.activeTabId === "string" ? parsed.activeTabId : null,
          };
        }
      } catch {
        saved = null;
      }
      setState({ projectId, tabs: saved?.tabs ?? [], isLoaded: true, hasSaved: saved !== null });
      if (saved && selectedIdRef.current === initialSelection) {
        selectRef.current(
          saved.tabs.some((tab) => tab.id === saved?.activeTabId) ? saved.activeTabId : null,
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, [kind, projectId]);

  useEffect(() => {
    if (!isHydrated) return;
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
      return { ...previous, projectId, tabs: next };
    });
  }, [projectId, selectedId, items, isLoaded, isHydrated]);

  useEffect(() => {
    if (!projectId || !isHydrated || (selectedId && !tabs.some((tab) => tab.id === selectedId)))
      return;
    void setPreference(
      `editor-tabs.${kind}.${projectId}`,
      JSON.stringify({ tabs, activeTabId: selectedId }),
    );
  }, [kind, projectId, isHydrated, selectedId, tabs]);

  const update = (fn: (tabs: EditorTab[]) => EditorTab[]) =>
    setState((previous) => ({
      ...previous,
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
    isLoaded: isHydrated,
    hasSaved: isHydrated && state.hasSaved,
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
