import { arrayMove } from "@dnd-kit/sortable";
import { Button, Dialog, Flex, Text, TextField } from "@radix-ui/themes";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  Search,
  UserRound,
} from "lucide-react";
import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { Virtuoso } from "react-virtuoso";

import { Spinner } from "@/components";
import {
  AssistantSidebar,
  type AssistantSidebarHandle,
  type AssistantSidebarState,
} from "@/features/assistant";
import {
  fetchChapters,
  fetchCharactersByProject,
  fetchTask,
  fetchWorldInfoByProject,
  fetchWorldInfoEntries,
  subscribeBackgroundEvents,
} from "@/lib/api-client";
import { getPreference, setPreference } from "@/lib/local-db";

import { useAppShell } from "./app-shell-context";
import { SidebarEntityEditor, type SidebarEntityKind } from "./right-sidebar-entity-editor";
import { RightSidebarTabs, type SidebarTab } from "./right-sidebar-tabs";

import "./right-sidebar.css";

interface RightSidebarProps {
  projectId: string;
  onStateChange?: (state: AssistantSidebarState) => void;
  onOpenMentionChapter?: (id: string, title: string) => void;
}

const INITIAL_TAB: SidebarTab = { id: "agent:initial", kind: "agent", title: "" };
const MAX_LOADED_TABS = 5;
const IDLE_STATE: AssistantSidebarState = { agentStatus: "idle", isAgentRunning: false };

export const RightSidebar = forwardRef<AssistantSidebarHandle, RightSidebarProps>(
  function RightSidebar({ projectId, onStateChange, onOpenMentionChapter }, ref) {
    const { t } = useTranslation();
    const { isMobile, closeAssistantSidebar, openAssistantSidebar } = useAppShell();
    const [tabs, setTabs] = useState<SidebarTab[]>([INITIAL_TAB]);
    const [activeId, setActiveId] = useState(INITIAL_TAB.id);
    const [loadedTabIds, setLoadedTabIds] = useState<string[]>([INITIAL_TAB.id]);
    const [pickerKind, setPickerKind] = useState<SidebarEntityKind | null>(null);
    const [agentStates, setAgentStates] = useState<Record<string, AssistantSidebarState>>({});
    const [isHydrated, setIsHydrated] = useState(false);
    const agentRefs = useRef(new Map<string, AssistantSidebarHandle>());
    const pendingMarkup = useRef<string[]>([]);
    const lastAgentId = useRef(INITIAL_TAB.id);
    const tabsRef = useRef(tabs);
    tabsRef.current = tabs;
    const prefix = useId();
    const hasUnloadedAgents = tabs.some(
      (tab) => tab.kind === "agent" && !loadedTabIds.includes(tab.id),
    );
    const unloadedAgentTabs = tabs.filter(
      (tab) =>
        tab.kind === "agent" &&
        tab.taskId &&
        !loadedTabIds.includes(tab.id) &&
        !agentStates[tab.id],
    );
    const unloadedTaskIds = [...new Set(unloadedAgentTabs.map((tab) => tab.taskId!))];
    const unloadedTaskQueries = useQueries({
      queries: unloadedTaskIds.map((taskId) => ({
        queryKey: ["task", taskId],
        queryFn: () => fetchTask(taskId),
        enabled: isHydrated,
      })),
    });
    const runningTabIds = tabs
      .filter((tab) => {
        if (tab.kind !== "agent") return false;
        const state = agentStates[tab.id];
        if (state) return state.isAgentRunning;
        const index = tab.taskId ? unloadedTaskIds.indexOf(tab.taskId) : -1;
        return index >= 0 && unloadedTaskQueries[index].data?.isRunning === true;
      })
      .map((tab) => tab.id);
    const isAgentRunning = runningTabIds.length > 0;
    const mobileAgent =
      tabs.find((tab) => tab.id === lastAgentId.current && tab.kind === "agent") ??
      tabs.find((tab) => tab.kind === "agent");
    const visibleTabId = isMobile ? (mobileAgent?.id ?? "") : activeId;

    useEffect(() => {
      let cancelled = false;
      void getPreference(`right-sidebar.tabs.${projectId}`).then((value) => {
        if (cancelled) return;
        try {
          const saved = value ? JSON.parse(value) : null;
          if (saved && Array.isArray(saved.tabs)) {
            const restored: SidebarTab[] = saved.tabs.filter(
              (tab: SidebarTab) =>
                typeof tab?.id === "string" &&
                typeof tab.title === "string" &&
                (tab.kind === "agent" ||
                  ((tab.kind === "chapter" ||
                    tab.kind === "character" ||
                    tab.kind === "world_info_entry") &&
                    typeof tab.entityId === "string")),
            );
            const active = restored.some((tab) => tab.id === saved.activeId)
              ? saved.activeId
              : (restored[0]?.id ?? "");
            setTabs(restored);
            setActiveId(active);
            setLoadedTabIds([
              ...restored
                .filter((tab) => tab.kind === "agent" && tab.id !== active)
                .slice(-(MAX_LOADED_TABS - 1))
                .map((tab) => tab.id),
              ...(active ? [active] : []),
            ]);
            lastAgentId.current =
              restored.find((tab) => tab.id === saved.lastAgentId && tab.kind === "agent")?.id ??
              restored.find((tab) => tab.kind === "agent")?.id ??
              "";
          }
        } catch {
          // Ignore invalid saved layout and keep the default tab.
        }
        setIsHydrated(true);
      });
      return () => {
        cancelled = true;
      };
    }, [projectId]);

    useEffect(() => {
      if (!isHydrated) return;
      void setPreference(
        `right-sidebar.tabs.${projectId}`,
        JSON.stringify({ tabs, activeId, lastAgentId: lastAgentId.current }),
      );
    }, [projectId, isHydrated, tabs, activeId]);

    useEffect(() => {
      if (!isMobile || !isHydrated || mobileAgent) return;
      lastAgentId.current = INITIAL_TAB.id;
      setTabs((current) =>
        current.some((tab) => tab.kind === "agent") ? current : [...current, INITIAL_TAB],
      );
    }, [isMobile, isHydrated, mobileAgent]);
    const activateTab = useCallback((id: string) => {
      setActiveId(id);
      if (!id) return;
      setLoadedTabIds((current) =>
        current.includes(id) ? current : [...current, id].slice(-MAX_LOADED_TABS),
      );
    }, []);

    useEffect(() => {
      if (!hasUnloadedAgents) return;
      const subscription = subscribeBackgroundEvents(projectId, (event) => {
        if (event.type !== "task_run_status_updated" || !event.task_id) return;
        const isRunning = event.is_running === true;
        setAgentStates((current) => {
          const next = { ...current };
          for (const tab of tabsRef.current) {
            const state = current[tab.id];
            if (
              tab.kind !== "agent" ||
              (state?.taskId ?? tab.taskId) !== event.task_id ||
              agentRefs.current.has(tab.id)
            )
              continue;
            next[tab.id] = {
              ...IDLE_STATE,
              ...state,
              taskId: event.task_id,
              isAgentRunning: isRunning,
              agentStatus: isRunning ? "running" : "idle",
            };
          }
          return next;
        });
      });
      return () => subscription.close();
    }, [hasUnloadedAgents, projectId]);

    const handleAgentStateChange = useCallback((id: string, state: AssistantSidebarState) => {
      setAgentStates((current) => ({ ...current, [id]: state }));
      setTabs((current) =>
        current.map((tab) =>
          tab.id === id && tab.kind === "agent" && tab.taskId !== (state.taskId ?? null)
            ? { ...tab, taskId: state.taskId ?? null }
            : tab,
        ),
      );
    }, []);
    const handleTitleChange = useCallback((id: string, title: string) => {
      setTabs((current) =>
        current.map((tab) => (tab.id === id && tab.title !== title ? { ...tab, title } : tab)),
      );
    }, []);
    const handleAppend = useCallback(
      (markup: string) => {
        if (!markup.trim()) return;
        openAssistantSidebar();
        const agentTab =
          tabs.find((tab) => tab.id === lastAgentId.current && tab.kind === "agent") ??
          tabs.find((tab) => tab.kind === "agent");
        const id = agentTab?.id ?? `agent:${crypto.randomUUID()}`;
        if (!agentTab) setTabs((current) => [...current, { id, kind: "agent", title: "" }]);
        lastAgentId.current = id;
        if (!isMobile) activateTab(id);
        const agent = agentRefs.current.get(id);
        if (agent) agent.appendToComposer(markup);
        else pendingMarkup.current.push(markup);
      },
      [activateTab, isMobile, openAssistantSidebar, tabs],
    );
    useImperativeHandle(ref, () => ({ appendToComposer: handleAppend }), [handleAppend]);

    useEffect(() => {
      const agent = agentRefs.current.get(visibleTabId);
      if (!agent || pendingMarkup.current.length === 0) return;
      pendingMarkup.current.splice(0).forEach((markup) => agent.appendToComposer(markup));
    }, [visibleTabId]);

    useEffect(() => {
      if (!isHydrated) return;
      const state = agentStates[visibleTabId] ?? agentStates[lastAgentId.current] ?? IDLE_STATE;
      onStateChange?.({ ...state, isAgentRunning });
    }, [visibleTabId, agentStates, isAgentRunning, onStateChange, isHydrated]);

    function handleCloseTabs(ids: string[]) {
      const closedIds = new Set(ids.filter((id) => !runningTabIds.includes(id)));
      const index = tabs.findIndex((tab) => tab.id === activeId);
      const remaining = tabs.filter((tab) => !closedIds.has(tab.id));
      setTabs(remaining);
      setLoadedTabIds((current) => current.filter((id) => !closedIds.has(id)));
      if (closedIds.has(activeId)) {
        const nextId = remaining[Math.min(index, remaining.length - 1)]?.id ?? "";
        activateTab(nextId);
        requestAnimationFrame(() => document.getElementById(`${prefix}-tab-${nextId}`)?.focus());
      }
      if (closedIds.has(lastAgentId.current))
        lastAgentId.current = remaining.find((tab) => tab.kind === "agent")?.id ?? "";
      setAgentStates((current) => {
        const next = { ...current };
        for (const id of closedIds) delete next[id];
        return next;
      });
    }

    function handleReorder(activeTabId: string, overTabId: string) {
      setTabs((current) => {
        const from = current.findIndex((tab) => tab.id === activeTabId);
        const to = current.findIndex((tab) => tab.id === overTabId);
        return from < 0 || to < 0 ? current : arrayMove(current, from, to);
      });
    }

    function handleActivateTab(tab: SidebarTab) {
      activateTab(tab.id);
      if (tab.kind === "agent") lastAgentId.current = tab.id;
    }

    function handleNewAgent() {
      const id = `agent:${crypto.randomUUID()}`;
      setTabs((current) => [...current, { id, kind: "agent", title: "" }]);
      activateTab(id);
      lastAgentId.current = id;
    }

    if (!isHydrated) return null;

    return (
      <div className="right-sidebar">
        {!isMobile && (
          <RightSidebarTabs
            tabs={tabs}
            activeId={activeId}
            prefix={prefix}
            runningTabIds={runningTabIds}
            onActivate={handleActivateTab}
            onClose={handleCloseTabs}
            onReorder={handleReorder}
            onNewAgent={handleNewAgent}
            onSelectKind={setPickerKind}
          />
        )}
        <div className="right-sidebar-body">
          {tabs
            .filter((tab) => loadedTabIds.includes(tab.id) || (isMobile && tab.id === visibleTabId))
            .toSorted((a, b) => a.id.localeCompare(b.id))
            .map((tab) => (
              <SidebarTabPanel
                key={tab.id}
                tab={tab}
                prefix={prefix}
                isActive={visibleTabId === tab.id}
                initialTaskId={agentStates[tab.id]?.taskId ?? tab.taskId}
                projectId={projectId}
                isMobile={isMobile}
                onClose={closeAssistantSidebar}
                isAgentLocked={isAgentRunning}
                agentRefs={agentRefs.current}
                onStateChange={handleAgentStateChange}
                onTitleChange={handleTitleChange}
                onAddToConversation={handleAppend}
                onOpenMentionChapter={onOpenMentionChapter}
              />
            ))}
          {!isMobile && tabs.length === 0 && (
            <Flex
              className="right-sidebar-placeholder"
              direction="column"
              align="center"
              justify="center"
              gap="2"
            >
              <Text
                size="2"
                color="gray"
              >
                {t("rightSidebar.empty")}
              </Text>
              <Text
                size="1"
                color="gray"
              >
                {t("rightSidebar.emptyHint")}
              </Text>
            </Flex>
          )}
        </div>
        {!isMobile && pickerKind && (
          <SidebarEntityPicker
            projectId={projectId}
            kind={pickerKind}
            onClose={() => setPickerKind(null)}
            onSelect={(entityId, title) => {
              const id = `${pickerKind}:${entityId}`;
              setTabs((current) =>
                current.some((tab) => tab.id === id)
                  ? current
                  : [...current, { id, kind: pickerKind, entityId, title }],
              );
              activateTab(id);
              setPickerKind(null);
            }}
          />
        )}
      </div>
    );
  },
);

interface SidebarTabPanelProps {
  tab: SidebarTab;
  prefix: string;
  isActive: boolean;
  initialTaskId?: string | null;
  projectId: string;
  isMobile: boolean;
  onClose: () => void;
  isAgentLocked: boolean;
  agentRefs: Map<string, AssistantSidebarHandle>;
  onStateChange: (id: string, state: AssistantSidebarState) => void;
  onTitleChange: (id: string, title: string) => void;
  onAddToConversation: (markup: string) => void;
  onOpenMentionChapter?: (id: string, title: string) => void;
}

function SidebarTabPanel({
  tab,
  prefix,
  isActive,
  initialTaskId,
  projectId,
  isMobile,
  onClose,
  isAgentLocked,
  agentRefs,
  onStateChange,
  onTitleChange,
  onAddToConversation,
  onOpenMentionChapter,
}: SidebarTabPanelProps) {
  const handleStateChange = useCallback(
    (state: AssistantSidebarState) => {
      onStateChange(tab.id, state);
      onTitleChange(tab.id, state.taskTitle ?? "");
    },
    [onStateChange, onTitleChange, tab.id],
  );
  const handleTitleChange = useCallback(
    (title: string) => onTitleChange(tab.id, title),
    [onTitleChange, tab.id],
  );
  const handleRef = useCallback(
    (handle: AssistantSidebarHandle | null) => {
      if (handle) agentRefs.set(tab.id, handle);
      else agentRefs.delete(tab.id);
    },
    [agentRefs, tab.id],
  );
  return (
    <div
      role={isMobile ? undefined : "tabpanel"}
      id={`${prefix}-panel-${tab.id}`}
      aria-labelledby={isMobile ? undefined : `${prefix}-tab-${tab.id}`}
      hidden={!isActive}
      className="right-sidebar-tab-panel"
      inert={!isActive}
    >
      {tab.kind === "agent" ? (
        <AssistantSidebar
          ref={handleRef}
          projectId={projectId}
          isMobileOverlay={isMobile}
          onClose={onClose}
          initialTaskId={initialTaskId}
          onStateChange={handleStateChange}
          onOpenMentionChapter={onOpenMentionChapter}
        />
      ) : (
        <SidebarEntityEditor
          kind={tab.kind}
          entityId={tab.entityId!}
          isAgentLocked={isAgentLocked}
          onTitleChange={handleTitleChange}
          onAddToConversation={onAddToConversation}
        />
      )}
    </div>
  );
}

function SidebarEntityPicker({
  projectId,
  kind,
  onClose,
  onSelect,
}: {
  projectId: string;
  kind: SidebarEntityKind;
  onClose: () => void;
  onSelect: (id: string, title: string) => void;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [expansion, setExpansion] = useState<{ query: string; values: Record<string, boolean> }>({
    query: "",
    values: {},
  });
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 200);
    return () => window.clearTimeout(timer);
  }, [search]);
  const results = useQuery({
    queryKey: ["right-sidebar-picker", projectId, kind, query],
    refetchOnMount: "always",
    queryFn: async ({
      signal,
    }): Promise<
      {
        id: string;
        title: string;
        count: number;
        children?: { id: string; title: string; count: number }[];
      }[]
    > => {
      if (kind === "chapter") {
        const tree = await fetchChapters(projectId, query, signal);
        return tree.volumes.map((volume) => ({
          id: volume.id,
          title: volume.title,
          count: volume.chapterCount,
          children: volume.chapters.map((chapter) => ({
            id: chapter.id,
            title: chapter.title,
            count: chapter.wordCount,
          })),
        }));
      }
      if (kind === "character") {
        const characters = await fetchCharactersByProject(projectId, query, signal);
        return characters.items.map((character) => ({
          id: character.id,
          title: character.name,
          count: character.tokenCount,
        }));
      }
      const worldInfo = await fetchWorldInfoByProject(projectId);
      const entries = await fetchWorldInfoEntries(worldInfo.id, query, signal);
      return entries.items.map((entry) => ({
        id: entry.id,
        title: entry.name,
        count: entry.tokenCount,
      }));
    },
  });
  const items = (results.data ?? []).flatMap((item) => {
    if (!item.children) return [{ ...item, isFolder: false, isChild: false, isExpanded: false }];
    const isExpanded =
      (expansion.query === query ? expansion.values[item.id] : undefined) ?? Boolean(query);
    return [
      { ...item, isFolder: true, isChild: false, isExpanded },
      ...(isExpanded
        ? item.children.map((child) => ({
            ...child,
            isFolder: false,
            isChild: true,
            isExpanded: false,
          }))
        : []),
    ];
  });
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Content
        maxWidth="360px"
        className="right-sidebar-picker"
        aria-describedby={undefined}
      >
        <Dialog.Title className="right-sidebar-picker-title">
          {t("rightSidebar.selectItem", { type: t(`rightSidebar.${kind}`) })}
        </Dialog.Title>
        <TextField.Root
          placeholder={t("rightSidebar.search")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label={t("rightSidebar.search")}
        >
          <TextField.Slot>
            <Search size={16} />
          </TextField.Slot>
        </TextField.Root>
        <div
          className="right-sidebar-picker-results"
          aria-busy={results.isFetching}
        >
          {results.isFetching || results.isPending ? (
            <Flex
              className="right-sidebar-picker-status"
              align="center"
              justify="center"
              direction="column"
              gap="2"
            >
              <Spinner
                size={18}
                aria-label={t("rightSidebar.loading")}
              />
              <Text
                size="1"
                color="gray"
              >
                {t("rightSidebar.loading")}
              </Text>
            </Flex>
          ) : results.isError ? (
            <Flex
              className="right-sidebar-picker-status"
              align="center"
              justify="center"
              direction="column"
              gap="2"
            >
              <Text
                color="gray"
                size="2"
              >
                {t("rightSidebar.loadFailed")}
              </Text>
              <Button
                variant="soft"
                onClick={() => void results.refetch()}
              >
                {t("common.retry")}
              </Button>
            </Flex>
          ) : items.length === 0 ? (
            <Flex
              className="right-sidebar-picker-status"
              align="center"
              justify="center"
            >
              <Text
                color="gray"
                size="2"
              >
                {t("rightSidebar.noResults")}
              </Text>
            </Flex>
          ) : (
            <Virtuoso
              className="right-sidebar-picker-list"
              data={items}
              computeItemKey={(_index, item) => `${item.isFolder ? "folder" : "item"}:${item.id}`}
              itemContent={(_index, item) => (
                <button
                  type="button"
                  className="right-sidebar-picker-item"
                  data-child={item.isChild}
                  aria-expanded={item.isFolder ? item.isExpanded : undefined}
                  onClick={() => {
                    if (!item.isFolder) return onSelect(item.id, item.title);
                    setExpansion((current) => ({
                      query,
                      values: {
                        ...(current.query === query ? current.values : {}),
                        [item.id]: !item.isExpanded,
                      },
                    }));
                  }}
                >
                  {item.isFolder ? (
                    item.isExpanded ? (
                      <ChevronDown size={14} />
                    ) : (
                      <ChevronRight size={14} />
                    )
                  ) : null}
                  {item.isFolder ? (
                    <Folder size={14} />
                  ) : kind === "chapter" ? (
                    <FileText size={14} />
                  ) : kind === "character" ? (
                    <UserRound size={14} />
                  ) : (
                    <BookOpen size={14} />
                  )}
                  <span className="right-sidebar-picker-item-title">{item.title}</span>
                  <span className="right-sidebar-picker-item-count">
                    {t(
                      item.isFolder
                        ? "rightSidebar.chapterCount"
                        : kind === "chapter"
                          ? "rightSidebar.wordCount"
                          : "rightSidebar.tokenCount",
                      { count: item.count },
                    )}
                  </span>
                </button>
              )}
            />
          )}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  );
}
