/**
 * World Info Page
 *
 * 世界书主页面，按项目展示对应世界书条目与编辑器。
 */

import { Box, Flex, Text, Dialog, Button, Skeleton, IconButton, Tooltip } from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, List } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Panel, Group, Separator } from "react-resizable-panels";
import { useSearchParams } from "react-router";

import "./world-info-page.css";

import { toast } from "@/components/toast";
import { MobileAppSidebarTrigger } from "@/features/app-shell";
import { AssistantSidebar } from "@/features/assistant";
import type { AssistantSidebarState } from "@/features/assistant";
import {
  fetchWorldInfoByProject,
  fetchProjects,
  fetchWorldInfoEntries,
  fetchWorldInfoEntry,
  createWorldInfoEntry,
  toggleWorldInfoEntry,
  deleteWorldInfoEntry,
  reorderWorldInfoEntries,
  batchDeleteWorldInfoEntries,
  batchToggleWorldInfoEntries,
} from "@/lib/api-client";
import { getPreference, setPreference } from "@/lib/local-db";
import type {
  WorldInfoEntry,
  WorldInfoEntryBrief,
  WorldInfoEntryBriefListResponse,
} from "@/lib/world-info.types";

import { EntryEditor } from "../components/entry-editor";
import { EntryList } from "../components/entry-list";
import { ImportWorldInfoDialog } from "../components/import-world-info-dialog";
import { useWorldInfoStore } from "../store/use-world-info-store";

const LAST_PROJECT_KEY = "worldInfo.lastProjectId";
const LAST_ENTRY_KEY = "worldInfo.lastEntryId";
const MotionBox = motion.create(Box);
const MOBILE_SIDEBAR_WIDTH = 320;

function generateUniqueEntryName(baseName: string, entries: WorldInfoEntryBrief[]): string {
  const normalizedName = baseName.trim();
  const existingNames = new Set(entries.map((entry) => entry.name));
  if (!existingNames.has(normalizedName)) return normalizedName;

  let counter = 1;
  while (existingNames.has(`${normalizedName} (${counter})`)) {
    counter += 1;
  }
  return `${normalizedName} (${counter})`;
}

export function WorldInfoPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const {
    currentWorldInfoId,
    setCurrentWorldInfo,
    currentEntryId,
    setCurrentEntry,
    sidebarOpen,
    setSidebarOpen,
    setFromWriting,
  } = useWorldInfoStore();

  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState<WorldInfoEntryBrief | null>(null);

  // 排序状态
  type SortField = "order" | "uid" | "tokenCount" | "name";
  type SortDirection = "asc" | "desc";
  const [sortField, setSortField] = useState<SortField>("order");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [isCreatingEntry, setIsCreatingEntry] = useState(false);
  const [scrollToLine, setScrollToLine] = useState<number | null>(null);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [assistantState, setAssistantState] = useState<AssistantSidebarState>({
    agentStatus: "idle",
    isAgentRunning: false,
  });
  const [isMobile, setIsMobile] = useState(false);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // 从 URL 参数初始化状态
  useEffect(() => {
    const projectId = searchParams.get("projectId");
    const from = searchParams.get("from");

    if (from === "writing" && projectId) {
      setFromWriting(true, projectId);
    }
  }, [searchParams, setFromWriting]);

  const { data: projectsData } = useQuery({
    queryKey: ["projects", "world-info-page"],
    queryFn: () => fetchProjects({ page: 1, pageSize: 100 }),
  });

  const projects = useMemo(() => projectsData?.items ?? [], [projectsData?.items]);
  const projectIdFromUrl = searchParams.get("projectId");

  useEffect(() => {
    const initProject = async () => {
      if (currentProjectId || projects.length === 0) return;
      const cachedProjectId = await getPreference(LAST_PROJECT_KEY);
      const nextProjectId =
        (projectIdFromUrl && projects.some((project) => project.id === projectIdFromUrl)
          ? projectIdFromUrl
          : null) ??
        (cachedProjectId && projects.some((project) => project.id === cachedProjectId)
          ? cachedProjectId
          : null) ??
        projects[0]?.id ??
        null;
      setCurrentProjectId(nextProjectId);
    };

    void initProject();
  }, [currentProjectId, projectIdFromUrl, projects]);

  useEffect(() => {
    if (currentProjectId) void setPreference(LAST_PROJECT_KEY, currentProjectId);
  }, [currentProjectId]);

  const { data: projectWorldInfo } = useQuery({
    queryKey: ["world-info-by-project", currentProjectId],
    queryFn: () => fetchWorldInfoByProject(currentProjectId!),
    enabled: !!currentProjectId,
  });

  useEffect(() => {
    setCurrentWorldInfo(projectWorldInfo?.id ?? null);
    setOptimisticEntries(null);
  }, [projectWorldInfo?.id, setCurrentWorldInfo]);

  useEffect(() => {
    if (!currentProjectId) {
      setCurrentWorldInfo(null);
      setCurrentEntry(null);
    }
  }, [currentProjectId, setCurrentEntry, setCurrentWorldInfo]);

  useEffect(() => {
    if (currentEntryId) void setPreference(LAST_ENTRY_KEY, currentEntryId);
  }, [currentEntryId]);

  // 获取条目列表（轻量，不含 content）
  const { data: entriesData, isLoading: entriesLoading } = useQuery({
    queryKey: ["world-info-entries", currentWorldInfoId],
    queryFn: () => fetchWorldInfoEntries(currentWorldInfoId!, { page: 1, pageSize: 500 }),
    enabled: !!currentWorldInfoId,
    staleTime: 0,
    gcTime: 0,
  });

  // 获取当前选中条目的完整数据
  const { data: selectedEntry, isLoading: isEntryLoading } = useQuery({
    queryKey: ["world-info-entry-detail", currentEntryId],
    queryFn: () => fetchWorldInfoEntry(currentEntryId!),
    enabled: !!currentEntryId,
    staleTime: 0,
    gcTime: 0,
  });

  // 使用本地状态管理条目列表，实现乐观更新
  const [optimisticEntries, setOptimisticEntries] = useState<WorldInfoEntryBrief[] | null>(null);

  // 派生最终的 entries：优先使用乐观更新，否则使用查询数据
  const entries = useMemo(() => {
    if (optimisticEntries !== null) {
      return optimisticEntries;
    }
    return entriesData?.items ?? [];
  }, [optimisticEntries, entriesData?.items]);

  useEffect(() => {
    const restoreEntry = async () => {
      if (!currentWorldInfoId || currentEntryId || entries.length === 0) return;
      const cachedEntryId = await getPreference(LAST_ENTRY_KEY);
      if (cachedEntryId && entries.some((entry) => entry.id === cachedEntryId)) {
        setCurrentEntry(cachedEntryId);
      }
    };

    void restoreEntry();
  }, [currentEntryId, currentWorldInfoId, entries, setCurrentEntry]);

  useEffect(() => {
    if (!currentEntryId || !entriesData) return;
    if (!entries.some((entry) => entry.id === currentEntryId)) {
      setCurrentEntry(null);
    }
  }, [currentEntryId, entries, entriesData, setCurrentEntry]);

  /** 从完整条目提取轻量字段，用于更新列表缓存 */
  const extractBrief = useCallback(
    (entry: WorldInfoEntry): WorldInfoEntryBrief => ({
      id: entry.id,
      worldInfoId: entry.worldInfoId,
      uid: entry.uid,
      name: entry.name,
      order: entry.order,
      tokenCount: entry.tokenCount,
      isEnabled: entry.isEnabled,
      createdAt: entry.createdAt,
      updatedAt: entry.updatedAt,
    }),
    [],
  );

  // 创建条目
  const createEntryMutation = useMutation({
    mutationFn: (name: string) =>
      createWorldInfoEntry(currentWorldInfoId!, {
        name,
      }),
    onSuccess: (newEntry) => {
      const brief = extractBrief(newEntry);
      queryClient.setQueryData(
        ["world-info-entries", currentWorldInfoId],
        (oldData: WorldInfoEntryBriefListResponse | undefined) => {
          if (!oldData) {
            return {
              items: [brief],
              total: 1,
              page: 1,
              pageSize: 500,
            };
          }

          return {
            ...oldData,
            items: [...oldData.items, brief],
            total: oldData.total + 1,
          };
        },
      );
      queryClient.setQueryData(["world-info-entry-detail", newEntry.id], newEntry);
      setCurrentEntry(newEntry.id);
    },
    onError: () => {
      toast.error(t("worldInfo.createFailed"));
    },
    onSettled: () => {
      setIsCreatingEntry(false);
    },
  });

  // 切换条目启用状态
  const toggleEntryMutation = useMutation({
    mutationFn: (entryId: string) => toggleWorldInfoEntry(entryId),
    onSuccess: (updatedEntry) => {
      toast.success(t("worldInfo.entryStatusUpdated"));
      setOptimisticEntries(null);
      const brief = extractBrief(updatedEntry);
      queryClient.setQueryData(
        ["world-info-entries", currentWorldInfoId],
        (oldData: WorldInfoEntryBriefListResponse | undefined) => {
          if (!oldData) return oldData;

          return {
            ...oldData,
            items: oldData.items.map((entry) => (entry.id === updatedEntry.id ? brief : entry)),
          };
        },
      );
    },
    onError: () => {
      toast.error(t("worldInfo.entryStatusUpdateFailed"));
      setOptimisticEntries(null);
      queryClient.invalidateQueries({
        queryKey: ["world-info-entries", currentWorldInfoId],
      });
    },
  });

  // 删除条目
  const deleteEntryMutation = useMutation({
    mutationFn: (entryId: string) => deleteWorldInfoEntry(entryId),
    onSuccess: () => {
      toast.success(t("worldInfo.entryDeleted"));
      setOptimisticEntries(null);
      queryClient.invalidateQueries({
        queryKey: ["world-info-entries", currentWorldInfoId],
      });
      if (entryToDelete && currentEntryId === entryToDelete.id) {
        setCurrentEntry(null);
      }
      setEntryToDelete(null);
      setDeleteDialogOpen(false);
    },
    onError: () => {
      toast.error(t("worldInfo.deleteFailed"));
      setDeleteDialogOpen(false);
    },
  });

  const handleSelectProject = useCallback(
    (projectId: string) => {
      setCurrentProjectId(projectId || null);
      setCurrentEntry(null);
      setIsCreatingEntry(false);
      setSidebarOpen(false);
      setIsAssistantOpen(false);
    },
    [setCurrentEntry, setSidebarOpen],
  );

  /** 处理创建条目 */
  const handleCreateEntry = useCallback(() => {
    if (currentWorldInfoId) {
      const name = generateUniqueEntryName(t("worldInfo.newEntry"), entries);
      setCurrentEntry(null);
      setIsCreatingEntry(true);
      createEntryMutation.mutate(name);
    }
  }, [currentWorldInfoId, createEntryMutation, entries, setCurrentEntry, t]);

  /** 处理选择条目 */
  const handleSelectEntry = useCallback(
    (entryId: string) => {
      setCurrentEntry(entryId);
      setSidebarOpen(false);
    },
    [setCurrentEntry, setSidebarOpen],
  );

  /** 处理切换条目启用状态 */
  const handleToggleEntry = useCallback(
    (entryId: string) => {
      const baseEntries = optimisticEntries ?? entries;
      const nextEntries = baseEntries.map((entry) =>
        entry.id === entryId ? { ...entry, isEnabled: !entry.isEnabled } : entry,
      );
      setOptimisticEntries(nextEntries);
      queryClient.setQueryData(
        ["world-info-entries", currentWorldInfoId],
        (oldData: WorldInfoEntryBriefListResponse | undefined) => {
          if (!oldData) return oldData;

          return {
            ...oldData,
            items: nextEntries,
          };
        },
      );
      toggleEntryMutation.mutate(entryId);
    },
    [currentWorldInfoId, entries, optimisticEntries, queryClient, toggleEntryMutation],
  );

  /** 处理删除条目确认 */
  const handleDeleteEntry = useCallback((entry: WorldInfoEntryBrief) => {
    setEntryToDelete(entry);
    setDeleteDialogOpen(true);
  }, []);

  /** 确认删除 */
  const handleConfirmDelete = useCallback(() => {
    if (entryToDelete) {
      deleteEntryMutation.mutate(entryToDelete.id);
    }
  }, [entryToDelete, deleteEntryMutation]);

  /** 乐观更新条目顺序 */
  const handleReorderEntries = useCallback(
    (reorderedEntries: WorldInfoEntryBrief[]) => {
      setOptimisticEntries(reorderedEntries);
      queryClient.setQueryData(
        ["world-info-entries", currentWorldInfoId],
        (oldData: WorldInfoEntryBriefListResponse | undefined) => {
          if (!oldData) {
            return {
              items: reorderedEntries,
              total: reorderedEntries.length,
              page: 1,
              pageSize: 500,
            };
          }
          return {
            ...oldData,
            items: reorderedEntries,
          };
        },
      );
    },
    [currentWorldInfoId, queryClient],
  );

  /** 批量保存拖拽排序 */
  const handleSaveDragOrder = useCallback(
    async (changes: Array<{ id: string; newOrder: number }>) => {
      try {
        const orders: Record<string, number> = {};
        changes.forEach((change) => {
          orders[change.id] = change.newOrder;
        });

        const updatedEntries = await reorderWorldInfoEntries(currentWorldInfoId!, orders);
        toast.success(t("worldInfo.entryOrderUpdated"));
        setOptimisticEntries(null);
        const briefEntries = updatedEntries.map(extractBrief);
        queryClient.setQueryData(
          ["world-info-entries", currentWorldInfoId],
          (oldData: WorldInfoEntryBriefListResponse | undefined) => {
            if (!oldData) return oldData;
            return {
              ...oldData,
              items: briefEntries,
            };
          },
        );
      } catch (error) {
        console.error("Failed to save drag order:", error);
        toast.error(t("worldInfo.entryOrderUpdateFailed"));
        setOptimisticEntries(null);
        queryClient.invalidateQueries({
          queryKey: ["world-info-entries", currentWorldInfoId],
        });
      }
    },
    [currentWorldInfoId, queryClient, t, extractBrief],
  );

  /** 处理排序切换 */
  const handleSortChange = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDirection("asc");
      }
    },
    [sortField],
  );

  /** 将条目置顶，本质为一次排序操作 */
  const handlePinEntry = useCallback(
    (entry: WorldInfoEntryBrief) => {
      const orderedEntries = [...entries].sort((a, b) => a.order - b.order);
      const currentIndex = orderedEntries.findIndex((item) => item.id === entry.id);
      if (currentIndex <= 0) return;

      const pinnedEntries = [
        orderedEntries[currentIndex],
        ...orderedEntries.slice(0, currentIndex),
        ...orderedEntries.slice(currentIndex + 1),
      ].map((item, index) => ({
        ...item,
        order: index + 1,
      }));

      handleReorderEntries(pinnedEntries);
      void handleSaveDragOrder(
        pinnedEntries.map((item) => ({ id: item.id, newOrder: item.order })),
      );
    },
    [entries, handleReorderEntries, handleSaveDragOrder],
  );

  /** 批量删除条目 */
  const handleBatchDelete = useCallback(
    (entryIds: string[]) => {
      if (!currentWorldInfoId) return;
      batchDeleteWorldInfoEntries(currentWorldInfoId, entryIds)
        .then((count) => {
          toast.success(t("worldInfo.batchDeleted", { count }));
          setOptimisticEntries(null);
          setCurrentEntry(null);
          queryClient.invalidateQueries({
            queryKey: ["world-info-entries", currentWorldInfoId],
          });
        })
        .catch(() => {
          toast.error(t("worldInfo.deleteFailed"));
        });
    },
    [currentWorldInfoId, queryClient, setCurrentEntry, t],
  );

  /** 批量切换条目开关 */
  const handleBatchToggle = useCallback(
    (entryIds: string[], isEnabled: boolean) => {
      if (!currentWorldInfoId) return;

      const idSet = new Set(entryIds);
      const nextEntries = entries.map((entry) =>
        idSet.has(entry.id) ? { ...entry, isEnabled } : entry,
      );
      setOptimisticEntries(nextEntries);

      batchToggleWorldInfoEntries(currentWorldInfoId, entryIds, isEnabled)
        .then((count) => {
          toast.success(t("worldInfo.batchToggled", { count }));
          setOptimisticEntries(null);
        })
        .catch(() => {
          toast.error(t("worldInfo.entryStatusUpdateFailed"));
          setOptimisticEntries(null);
          queryClient.invalidateQueries({
            queryKey: ["world-info-entries", currentWorldInfoId],
          });
        });
    },
    [currentWorldInfoId, entries, queryClient, t],
  );

  /** 处理从搜索面板导航到匹配行 */
  const handleNavigateToMatch = useCallback(
    (entryId: string, lineNumber: number) => {
      setCurrentEntry(entryId);
      setScrollToLine(lineNumber);
    },
    [setCurrentEntry],
  );

  /** 滚动完成后清除 */
  const handleScrollComplete = useCallback(() => {
    setScrollToLine(null);
  }, []);

  // 当前选中的条目（从详情查询获取完整数据）
  // selectedEntry 来自 useQuery，已在上方声明

  const isAgentLocked = Boolean(currentProjectId && assistantState.isAgentRunning);

  // 侧边栏内容
  const sidebarContent = currentProjectId ? (
    <EntryList
      projects={projects}
      currentProjectId={currentProjectId}
      onSelectProject={handleSelectProject}
      onImport={() => setImportDialogOpen(true)}
      entries={entries}
      onCreateEntry={handleCreateEntry}
      onSelectEntry={handleSelectEntry}
      onToggleEntry={handleToggleEntry}
      onDeleteEntry={handleDeleteEntry}
      onPinEntry={handlePinEntry}
      onReorderEntries={handleReorderEntries}
      onSaveDragOrder={handleSaveDragOrder}
      isLoading={entriesLoading}
      sortField={sortField}
      sortDirection={sortDirection}
      onSortChange={handleSortChange}
      onBatchDelete={handleBatchDelete}
      onBatchToggle={handleBatchToggle}
      onNavigateToMatch={handleNavigateToMatch}
    />
  ) : (
    <Flex
      align="center"
      justify="center"
      height="100%"
      p="4"
    >
      <Text
        size="2"
        color="gray"
        align="center"
      >
        {t("worldInfo.noProject")}
      </Text>
    </Flex>
  );

  const agentSidebarContent = currentProjectId ? (
    <AssistantSidebar
      projectId={currentProjectId}
      onStateChange={setAssistantState}
      onClose={() => setIsAssistantOpen(false)}
      isMobileOverlay={isMobile}
    />
  ) : (
    <Flex
      align="center"
      justify="center"
      height="100%"
      p="4"
    >
      <Text
        size="2"
        color="gray"
        align="center"
      >
        {t("worldInfo.noProject")}
      </Text>
    </Flex>
  );

  const editorContent = isCreatingEntry ? (
    <Box p="4">
      <Flex
        direction="column"
        gap="4"
        style={{ maxWidth: 800, margin: "0 auto" }}
      >
        <Skeleton
          width="120px"
          height="14px"
        />
        <Skeleton
          width="100%"
          height="36px"
        />
        <Flex gap="4">
          <Skeleton
            style={{ flex: 1 }}
            height="36px"
          />
          <Skeleton
            style={{ flex: 1 }}
            height="36px"
          />
        </Flex>
        <Skeleton
          width="100%"
          height="200px"
        />
        <Skeleton
          width="100%"
          height="80px"
        />
      </Flex>
    </Box>
  ) : selectedEntry ? (
    <EntryEditor
      key={selectedEntry.id}
      entry={selectedEntry}
      worldInfoId={currentWorldInfoId!}
      entries={entries}
      scrollToLine={scrollToLine}
      onScrollComplete={handleScrollComplete}
      isAgentLocked={isAgentLocked}
    />
  ) : currentEntryId && isEntryLoading ? (
    <Box p="4">
      <Flex
        direction="column"
        gap="4"
        style={{ maxWidth: 800, margin: "0 auto" }}
      >
        <Skeleton
          width="120px"
          height="14px"
        />
        <Skeleton
          width="100%"
          height="36px"
        />
        <Flex gap="4">
          <Skeleton
            style={{ flex: 1 }}
            height="36px"
          />
          <Skeleton
            style={{ flex: 1 }}
            height="36px"
          />
        </Flex>
        <Skeleton
          width="100%"
          height="200px"
        />
        <Skeleton
          width="100%"
          height="80px"
        />
      </Flex>
    </Box>
  ) : (
    <Flex
      align="center"
      justify="center"
      height="100%"
      direction="column"
      gap="2"
    >
      <Text
        size="3"
        color="gray"
      >
        {t("worldInfo.selectEntry")}
      </Text>
    </Flex>
  );

  return (
    <Box
      style={{
        height: "100%",
        minHeight: 0,
        overflow: "hidden",
      }}
    >
      <Box
        style={{
          height: "100%",
          minHeight: 0,
          overflow: "hidden",
        }}
      >
        <Flex
          direction="column"
          style={{ height: "100%", minHeight: 0 }}
        >
          {!isMobile && currentProjectId ? (
            <Group
              orientation="horizontal"
              className="world-info-page-group"
            >
              <Panel
                id="left-sidebar"
                defaultSize={300}
                minSize={250}
                maxSize={400}
                collapsible={false}
              >
                <Box className="world-info-page-sidebar world-info-page-sidebar--left">
                  {sidebarContent}
                </Box>
              </Panel>

              <Separator className="resize-handle world-info-page-separator" />

              <Panel
                id="editor"
                minSize={30}
              >
                <Box
                  data-scroll-container
                  className="world-info-page-editor-shell"
                >
                  {editorContent}
                </Box>
              </Panel>

              <Separator className="resize-handle world-info-page-separator" />

              <Panel
                id="right-sidebar"
                defaultSize={500}
                minSize={300}
                maxSize={600}
                collapsible={false}
              >
                <Box className="world-info-page-sidebar world-info-page-sidebar--right">
                  {agentSidebarContent}
                </Box>
              </Panel>
            </Group>
          ) : currentProjectId ? (
            <Flex className="world-info-page-mobile-layout">
              <Box className="world-info-page-editor-shell world-info-page-editor-shell--mobile">
                <Flex
                  align="center"
                  justify="between"
                  px="3"
                  py="2"
                  className="world-info-page-mobile-topbar"
                >
                  <Flex
                    align="center"
                    gap="1"
                  >
                    <MobileAppSidebarTrigger />
                    <Tooltip content={t("worldInfo.entries")}>
                      <IconButton
                        variant="ghost"
                        size="2"
                        aria-label={t("worldInfo.entries")}
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                      >
                        <List size={18} />
                      </IconButton>
                    </Tooltip>
                  </Flex>

                  <Tooltip content={t("assistant.mobileTitle")}>
                    <IconButton
                      variant="ghost"
                      size="2"
                      aria-label={t("assistant.mobileTitle")}
                      onClick={() => setIsAssistantOpen(true)}
                    >
                      <Bot size={18} />
                    </IconButton>
                  </Tooltip>
                </Flex>

                <Box
                  data-scroll-container
                  className="world-info-page-content-fill"
                >
                  {editorContent}
                </Box>

                <motion.div
                  initial={false}
                  animate={{ opacity: sidebarOpen ? 1 : 0 }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  onClick={() => setSidebarOpen(false)}
                  className="world-info-page-mobile-sidebar-backdrop"
                  style={{ pointerEvents: sidebarOpen ? "auto" : "none" }}
                />

                <MotionBox
                  initial={false}
                  animate={{ x: sidebarOpen ? 0 : -MOBILE_SIDEBAR_WIDTH }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  className="world-info-page-mobile-sidebar-sheet"
                  style={{
                    width: MOBILE_SIDEBAR_WIDTH,
                    minWidth: MOBILE_SIDEBAR_WIDTH,
                    pointerEvents: sidebarOpen ? "auto" : "none",
                  }}
                >
                  {sidebarContent}
                </MotionBox>
              </Box>
            </Flex>
          ) : (
            <Flex
              align="center"
              justify="center"
              height="100%"
              direction="column"
              gap="2"
            >
              <Text
                size="3"
                weight="medium"
              >
                {t("worldInfo.noProject")}
              </Text>
              <Text
                size="2"
                color="gray"
              >
                {t("worldInfo.noProjectHint")}
              </Text>
            </Flex>
          )}
        </Flex>
      </Box>

      {isMobile && currentProjectId && (
        <MotionBox
          initial={false}
          animate={{ x: isAssistantOpen ? 0 : "100%" }}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          className="world-info-page-mobile-assistant-overlay"
          data-open={isAssistantOpen}
          aria-hidden={!isAssistantOpen}
        >
          {agentSidebarContent}
        </MotionBox>
      )}

      <ImportWorldInfoDialog
        open={importDialogOpen}
        worldInfoId={currentWorldInfoId}
        onOpenChange={setImportDialogOpen}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["world-info-entries", currentWorldInfoId] });
        }}
      />

      {/* 删除确认对话框 */}
      <Dialog.Root
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
      >
        <Dialog.Content style={{ maxWidth: 400 }}>
          <Dialog.Title>{t("worldInfo.deleteEntry")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mb="4"
          >
            {t("worldInfo.deleteEntryConfirm", { name: entryToDelete?.name })}
          </Dialog.Description>
          <Flex
            gap="3"
            justify="end"
          >
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              variant="solid"
              color="red"
              onClick={handleConfirmDelete}
              disabled={deleteEntryMutation.isPending}
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
