/**
 * World Info Page
 *
 * 世界书主页面，包含世界书选择器、条目列表和条目编辑器。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import {
  Box,
  Flex,
  Text,
  Dialog,
  Button,
  Skeleton,
  IconButton,
  Tooltip,
} from "@radix-ui/themes";
import { motion } from "motion/react";
import { List } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";


import { MobileAppSidebarTrigger } from "@/features/app-shell/components/mobile-app-sidebar-trigger";
import { WorldInfoSelector } from "../components/world-info-selector";
import { EntryList } from "../components/entry-list";
import { EntryEditor } from "../components/entry-editor";
import { useWorldInfoStore } from "../store/use-world-info-store";
import { toast } from "@/components/toast";
import {
  fetchWorldInfoByProject,
  createWorldInfo,
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
import type { WorldInfoEntry, WorldInfoEntryBrief, WorldInfoEntryBriefListResponse } from "@/lib/world-info.types";

const MotionBox = motion.create(Box);

export function WorldInfoPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const {
    currentWorldInfoId,
    setCurrentWorldInfo,
    currentEntryId,
    setCurrentEntry,
    setFromWriting,
    sidebarOpen,
    setSidebarOpen,
  } = useWorldInfoStore();

  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState<WorldInfoEntryBrief | null>(
    null
  );

  // 排序状态
  type SortField = "order" | "uid" | "tokenCount" | "name";
  type SortDirection = "asc" | "desc";
  const [sortField, setSortField] = useState<SortField>("order");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [isCreatingEntry, setIsCreatingEntry] = useState(false);
  const [scrollToLine, setScrollToLine] = useState<number | null>(null);
  // 响应式检测
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

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

  // 如果从写作页面进入且有 projectId，查找对应的世界书
  const projectIdFromUrl = searchParams.get("projectId");
  const { data: projectWorldInfo } = useQuery({
    queryKey: ["world-info-by-project", projectIdFromUrl],
    queryFn: () => fetchWorldInfoByProject(projectIdFromUrl!),
    enabled: !!projectIdFromUrl && !currentWorldInfoId,
  });

  // 如果找到了项目的世界书，自动选中
  useEffect(() => {
    if (projectWorldInfo && !currentWorldInfoId) {
      setCurrentWorldInfo(projectWorldInfo.id);
    }
  }, [projectWorldInfo, currentWorldInfoId, setCurrentWorldInfo]);

  // 如果从写作页面进入但项目没有世界书，自动创建
  const createWorldInfoMutation = useMutation({
    mutationFn: () =>
      createWorldInfo({
        name: t("worldInfo.title"),
        projectId: projectIdFromUrl ?? undefined,
      }),
    onSuccess: (newWorldInfo) => {
      queryClient.invalidateQueries({ queryKey: ["world-info-list"] });
      queryClient.invalidateQueries({
        queryKey: ["world-info-by-project", projectIdFromUrl],
      });
      setCurrentWorldInfo(newWorldInfo.id);
    },
  });

  useEffect(() => {
    if (
      projectIdFromUrl &&
      projectWorldInfo === null &&
      !currentWorldInfoId &&
      !createWorldInfoMutation.isPending
    ) {
      createWorldInfoMutation.mutate();
    }
  }, [
    projectIdFromUrl,
    projectWorldInfo,
    currentWorldInfoId,
    createWorldInfoMutation,
  ]);

  // 如果没有 URL 参数，从缓存恢复上次选择
  useEffect(() => {
    if (!projectIdFromUrl) {
      const restore = async () => {
        const cachedWorldInfoId = await getPreference("worldInfo.lastWorldInfoId");
        const cachedEntryId = await getPreference("worldInfo.lastEntryId");
        if (cachedWorldInfoId) {
          setCurrentWorldInfo(cachedWorldInfoId);
          if (cachedEntryId) {
            setCurrentEntry(cachedEntryId);
          }
        }
      };
      void restore();
    }
  }, [projectIdFromUrl, setCurrentWorldInfo, setCurrentEntry]);

  // 持久化当前选择
  useEffect(() => {
    void setPreference("worldInfo.lastWorldInfoId", currentWorldInfoId ?? "");
    void setPreference("worldInfo.lastEntryId", currentEntryId ?? "");
  }, [currentWorldInfoId, currentEntryId]);

  // 获取条目列表（轻量，不含 content）
  const { data: entriesData, isLoading: entriesLoading } = useQuery({
    queryKey: ["world-info-entries", currentWorldInfoId],
    queryFn: () =>
      fetchWorldInfoEntries(currentWorldInfoId!, { page: 1, pageSize: 500 }),
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

  /** 从完整条目提取轻量字段，用于更新列表缓存 */
  const extractBrief = useCallback((entry: WorldInfoEntry): WorldInfoEntryBrief => ({
    id: entry.id,
    worldInfoId: entry.worldInfoId,
    uid: entry.uid,
    name: entry.name,
    order: entry.order,
    tokenCount: entry.tokenCount,
    isEnabled: entry.isEnabled,
    createdAt: entry.createdAt,
    updatedAt: entry.updatedAt,
  }), []);

  // 创建条目
  const createEntryMutation = useMutation({
    mutationFn: () =>
      createWorldInfoEntry(currentWorldInfoId!, {
        name: t("worldInfo.newEntry"),
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
        }
      );
      queryClient.setQueryData(
        ["world-info-entry-detail", newEntry.id],
        newEntry,
      );
      setCurrentEntry(newEntry.id);
      // 移动端创建后关闭侧边栏
      if (isMobile) {
        setSidebarOpen(false);
      }
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
            items: oldData.items.map((entry) =>
              entry.id === updatedEntry.id ? brief : entry
            ),
          };
        }
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

  /** 处理世界书选择 */
  const handleWorldInfoChange = useCallback(
    (worldInfoId: string) => {
      setCurrentWorldInfo(worldInfoId);
      setCurrentEntry(null);
    },
    [setCurrentWorldInfo, setCurrentEntry]
  );

  /** 处理创建条目 */
  const handleCreateEntry = useCallback(() => {
    if (currentWorldInfoId) {
      setCurrentEntry(null);
      setIsCreatingEntry(true);
      createEntryMutation.mutate();
    }
  }, [currentWorldInfoId, createEntryMutation, setCurrentEntry]);

  /** 处理选择条目 */
  const handleSelectEntry = useCallback(
    (entryId: string) => {
      setCurrentEntry(entryId);
      // 移动端选择后关闭侧边栏
      if (isMobile) {
        setSidebarOpen(false);
      }
    },
    [setCurrentEntry, isMobile, setSidebarOpen]
  );

  /** 处理切换条目启用状态 */
  const handleToggleEntry = useCallback(
    (entryId: string) => {
      const baseEntries = optimisticEntries ?? entries;
      const nextEntries = baseEntries.map((entry) =>
        entry.id === entryId
          ? { ...entry, isEnabled: !entry.isEnabled }
          : entry
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
        }
      );
      toggleEntryMutation.mutate(entryId);
    },
    [currentWorldInfoId, entries, optimisticEntries, queryClient, toggleEntryMutation]
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
        }
      );
    },
    [currentWorldInfoId, queryClient]
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
          }
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
    [currentWorldInfoId, queryClient, t, extractBrief]
  );

  /** 切换移动端侧边栏 */
  const handleToggleSidebar = useCallback(() => {
    setSidebarOpen(!sidebarOpen);
  }, [sidebarOpen, setSidebarOpen]);

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
    [sortField]
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
        pinnedEntries.map((item) => ({ id: item.id, newOrder: item.order }))
      );
    },
    [entries, handleReorderEntries, handleSaveDragOrder]
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
    [currentWorldInfoId, queryClient, setCurrentEntry, t]
  );

  /** 批量切换条目开关 */
  const handleBatchToggle = useCallback(
    (entryIds: string[], isEnabled: boolean) => {
      if (!currentWorldInfoId) return;

      const idSet = new Set(entryIds);
      const nextEntries = entries.map((entry) =>
        idSet.has(entry.id) ? { ...entry, isEnabled } : entry
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
    [currentWorldInfoId, entries, queryClient, t]
  );

  /** 处理从搜索面板导航到匹配行 */
  const handleNavigateToMatch = useCallback(
    (entryId: string, lineNumber: number) => {
      setCurrentEntry(entryId);
      setScrollToLine(lineNumber);
    },
    [setCurrentEntry]
  );

  /** 滚动完成后清除 */
  const handleScrollComplete = useCallback(() => {
    setScrollToLine(null);
  }, []);

  // 当前选中的条目（从详情查询获取完整数据）
  // selectedEntry 来自 useQuery，已在上方声明

  // 侧边栏宽度
  const sidebarWidth = 320;

  // 侧边栏内容
  const sidebarContent = currentWorldInfoId ? (
    <EntryList
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
    <Flex align="center" justify="center" height="100%" p="4">
      <Text size="2" color="gray" align="center">
        {t("worldInfo.selectWorldInfo")}
      </Text>
    </Flex>
  );

  const mobileEntrySidebarTrigger = isMobile ? (
    <Tooltip content={t("worldInfo.viewEntries")}>
      <IconButton
        variant="ghost"
        size="2"
        aria-label={t("worldInfo.viewEntries")}
        onClick={handleToggleSidebar}
      >
        <List size={18} />
      </IconButton>
    </Tooltip>
  ) : null;

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
        <Flex direction="column" style={{ height: "100%", minHeight: 0 }}>
          <WorldInfoSelector
            value={currentWorldInfoId}
            onChange={handleWorldInfoChange}
            isMobile={isMobile}
            appSidebarTrigger={isMobile ? <MobileAppSidebarTrigger /> : null}
            entrySidebarTrigger={mobileEntrySidebarTrigger}
          />

          {/* 三栏布局 */}
          <Flex
            style={{
              flex: 1,
              minHeight: 0,
              background: "var(--gray-a2)",
              overflow: "hidden",
              position: "relative",
            }}
          >
            {/* 左侧条目列表（桌面端） */}
            {!isMobile && (
              <Box
                className="worldInfoSidebar"
                style={{
                  width: sidebarWidth,
                  flexShrink: 0,
                  height: "100%",
                  minHeight: 0,
                  borderRight: "1px solid var(--gray-a4)",
                  background: "var(--color-background)",
                }}
              >
                {sidebarContent}
              </Box>
            )}

            {/* 中间编辑器区域 */}
            <Box
              data-scroll-container
              style={{
                flex: 1,
                height: "100%",
                minHeight: 0,
                overflowY: "auto",
                background: "var(--color-background)",
              }}
            >
              {isCreatingEntry ? (
                <Box p="4">
                  <Flex direction="column" gap="4" style={{ maxWidth: 800, margin: "0 auto" }}>
                    <Skeleton width="120px" height="14px" />
                    <Skeleton width="100%" height="36px" />
                    <Flex gap="4">
                      <Skeleton style={{ flex: 1 }} height="36px" />
                      <Skeleton style={{ flex: 1 }} height="36px" />
                    </Flex>
                    <Skeleton width="100%" height="200px" />
                    <Skeleton width="100%" height="80px" />
                  </Flex>
                </Box>
              ) : selectedEntry ? (
                <EntryEditor
                  key={selectedEntry.id}
                  entry={selectedEntry}
                  worldInfoId={currentWorldInfoId!}
                  scrollToLine={scrollToLine}
                  onScrollComplete={handleScrollComplete}
                />
              ) : currentEntryId && isEntryLoading ? (
                <Box p="4">
                  <Flex direction="column" gap="4" style={{ maxWidth: 800, margin: "0 auto" }}>
                    <Skeleton width="120px" height="14px" />
                    <Skeleton width="100%" height="36px" />
                    <Flex gap="4">
                      <Skeleton style={{ flex: 1 }} height="36px" />
                      <Skeleton style={{ flex: 1 }} height="36px" />
                    </Flex>
                    <Skeleton width="100%" height="200px" />
                    <Skeleton width="100%" height="80px" />
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
                  <Text size="3" color="gray">
                    {currentWorldInfoId
                      ? t("worldInfo.selectEntry")
                      : t("worldInfo.selectWorldInfo")}
                  </Text>
                </Flex>
              )}
            </Box>

            {/* 右侧空白侧边栏（占位） */}
            {!isMobile && (
              <Box
                className="worldInfoRightSidebar"
                style={{
                  width: sidebarWidth,
                  flexShrink: 0,
                  height: "100%",
                  minHeight: 0,
                  borderLeft: "1px solid var(--gray-a4)",
                  background: "var(--color-background)",
                }}
              />
            )}

            {isMobile && (
              <>
                <motion.div
                  initial={false}
                  animate={{ opacity: sidebarOpen ? 1 : 0 }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  onClick={() => setSidebarOpen(false)}
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: "rgba(0, 0, 0, 0.5)",
                    zIndex: 10,
                    pointerEvents: sidebarOpen ? "auto" : "none",
                  }}
                />

                <MotionBox
                  initial={false}
                  animate={{ x: sidebarOpen ? 0 : -sidebarWidth }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: sidebarWidth,
                    minWidth: sidebarWidth,
                    height: "100%",
                    background: "var(--color-background)",
                    borderRight: "1px solid var(--gray-a4)",
                    zIndex: 11,
                    overflow: "hidden",
                    pointerEvents: sidebarOpen ? "auto" : "none",
                    willChange: "transform",
                  }}
                >
                  {sidebarContent}
                </MotionBox>
              </>
            )}
          </Flex>
        </Flex>
      </Box>

      {/* 删除确认对话框 */}
      <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <Dialog.Content style={{ maxWidth: 400 }}>
          <Dialog.Title>{t("worldInfo.deleteEntry")}</Dialog.Title>
          <Dialog.Description size="2" mb="4">
            {t("worldInfo.deleteEntryConfirm", { name: entryToDelete?.name })}
          </Dialog.Description>
          <Flex gap="3" justify="end">
            <Dialog.Close>
              <Button variant="soft" color="gray">
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
