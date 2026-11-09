import { arrayMove } from "@dnd-kit/sortable";
import { Button, Dialog, Flex, Text, TextField } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
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
  fetchWorldInfoByProject,
  fetchWorldInfoEntries,
  subscribeBackgroundEvents,
} from "@/lib/api-client";

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
    const { closeAssistantSidebar, openAssistantSidebar } = useAppShell();
    const [tabs, setTabs] = useState<SidebarTab[]>([INITIAL_TAB]);
    const [activeId, setActiveId] = useState(INITIAL_TAB.id);
    const [loadedTabIds, setLoadedTabIds] = useState<string[]>([INITIAL_TAB.id]);
    const [pickerKind, setPickerKind] = useState<SidebarEntityKind | null>(null);
    const [agentStates, setAgentStates] = useState<Record<string, AssistantSidebarState>>({});
    const agentRefs = useRef(new Map<string, AssistantSidebarHandle>());
    const pendingMarkup = useRef<string[]>([]);
    const lastAgentId = useRef(INITIAL_TAB.id);
    const prefix = useId();
    const isAgentRunning = Object.values(agentStates).some((state) => state.isAgentRunning);
    const hasUnloadedAgents = tabs.some(
      (tab) => tab.kind === "agent" && !loadedTabIds.includes(tab.id),
    );
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
          for (const [id, state] of Object.entries(current)) {
            if (state.taskId !== event.task_id || agentRefs.current.has(id)) continue;
            next[id] = {
              ...state,
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
        activateTab(id);
        const agent = agentRefs.current.get(id);
        if (agent) agent.appendToComposer(markup);
        else pendingMarkup.current.push(markup);
      },
      [activateTab, openAssistantSidebar, tabs],
    );
    useImperativeHandle(ref, () => ({ appendToComposer: handleAppend }), [handleAppend]);

    useEffect(() => {
      const agent = agentRefs.current.get(activeId);
      if (!agent || pendingMarkup.current.length === 0) return;
      pendingMarkup.current.splice(0).forEach((markup) => agent.appendToComposer(markup));
    }, [activeId]);

    useEffect(() => {
      const state = agentStates[activeId] ?? agentStates[lastAgentId.current] ?? IDLE_STATE;
      onStateChange?.({ ...state, isAgentRunning });
    }, [activeId, agentStates, isAgentRunning, onStateChange]);

    function handleCloseTabs(ids: string[]) {
      const closedIds = new Set(ids.filter((id) => !agentStates[id]?.isAgentRunning));
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

    return (
      <div className="right-sidebar">
        <RightSidebarTabs
          tabs={tabs}
          activeId={activeId}
          prefix={prefix}
          runningTabIds={Object.entries(agentStates)
            .filter(([, state]) => state.isAgentRunning)
            .map(([id]) => id)}
          onActivate={handleActivateTab}
          onClose={handleCloseTabs}
          onReorder={handleReorder}
          onNewAgent={handleNewAgent}
          onSelectKind={setPickerKind}
          onCollapse={closeAssistantSidebar}
        />
        <div className="right-sidebar-body">
          {tabs
            .filter((tab) => loadedTabIds.includes(tab.id))
            .toSorted((a, b) => a.id.localeCompare(b.id))
            .map((tab) => (
              <SidebarTabPanel
                key={tab.id}
                tab={tab}
                prefix={prefix}
                isActive={activeId === tab.id}
                initialTaskId={agentStates[tab.id]?.taskId}
                projectId={projectId}
                isAgentLocked={isAgentRunning}
                agentRefs={agentRefs.current}
                onStateChange={handleAgentStateChange}
                onTitleChange={handleTitleChange}
                onAddToConversation={handleAppend}
                onOpenMentionChapter={onOpenMentionChapter}
              />
            ))}
          {tabs.length === 0 && (
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
        {pickerKind && (
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
      role="tabpanel"
      id={`${prefix}-panel-${tab.id}`}
      aria-labelledby={`${prefix}-tab-${tab.id}`}
      hidden={!isActive}
      className="right-sidebar-tab-panel"
      inert={!isActive}
    >
      {tab.kind === "agent" ? (
        <AssistantSidebar
          ref={handleRef}
          projectId={projectId}
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
