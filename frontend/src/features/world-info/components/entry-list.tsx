/**
 * Entry List Component
 *
 * 世界书条目列表组件，包含搜索、排序和重排序功能。
 */

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  type DragMoveEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  Box,
  Flex,
  Text,
  IconButton,
  Tooltip,
  DropdownMenu,
  Skeleton,
  Dialog,
  Button,
} from "@radix-ui/themes";
import {
  Search,
  Plus,
  Upload,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Pin,
  Trash2,
  ListChecks,
  CheckSquare,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
import { flushSync } from "react-dom";
import { useTranslation } from "react-i18next";
import { Virtuoso } from "react-virtuoso";

import { ProjectSelectField } from "@/components";
import { ContextMenu, type ContextMenuItem } from "@/components/context-menu";
import type { Project } from "@/lib/project.types";
import type { WorldInfoEntryBrief } from "@/lib/world-info.types";

import { useWorldInfoStore } from "../store/use-world-info-store";
import {
  ENTRY_LIST_ITEM_HEIGHT,
  getAutoScrollSpeed,
  getDragTargetIndex,
  getEntryDragOffset,
  reorderEntries,
} from "./entry-list-drag";
import { EntryListItem } from "./entry-list-item";
import { EntrySearchPopover } from "./entry-search-popover";

/** 排序字段 */
type SortField = "order" | "uid" | "tokenCount" | "name";
/** 排序方向 */
type SortDirection = "asc" | "desc";

const VIRTUAL_LIST_OVERSCAN = 320;

interface EntryListProps {
  projects: Project[];
  currentProjectId: string;
  onSelectProject: (projectId: string) => void;
  onImport: () => void;
  /** 条目列表 */
  entries: WorldInfoEntryBrief[];
  /** 新建条目回调 */
  onCreateEntry: () => void;
  /** 选择条目回调 */
  onSelectEntry: (entryId: string) => void;
  /** 切换条目启用状态回调 */
  onToggleEntry: (entryId: string) => void;
  /** 删除条目回调 */
  onDeleteEntry: (entry: WorldInfoEntryBrief) => void;
  /** 置顶条目回调 */
  onPinEntry: (entry: WorldInfoEntryBrief) => void;
  /** 重新排序条目回调（乐观更新） */
  onReorderEntries: (reorderedEntries: WorldInfoEntryBrief[]) => void;
  /** 保存单条拖拽排序回调 */
  onSaveDragOrder?: (entryId: string, newOrder: number) => Promise<void> | void;
  /** 是否正在加载 */
  isLoading?: boolean;
  /** 排序字段 */
  sortField: SortField;
  /** 排序方向 */
  sortDirection: SortDirection;
  /** 排序变更回调 */
  onSortChange: (field: SortField) => void;
  /** 批次删除回调 */
  onBatchDelete: (entryIds: string[]) => void;
  /** 批次切换开关回调 */
  onBatchToggle: (entryIds: string[], isEnabled: boolean) => void;
  /** 从搜索面板导航到匹配行 */
  onNavigateToMatch: (entryId: string, lineNumber: number) => void;
}

interface ContextMenuPosition {
  x: number;
  y: number;
}

export function EntryList({
  projects,
  currentProjectId,
  onSelectProject,
  onImport,
  entries,
  onCreateEntry,
  onSelectEntry,
  onToggleEntry,
  onDeleteEntry,
  onPinEntry,
  onReorderEntries,
  onSaveDragOrder,
  isLoading,
  sortField,
  sortDirection,
  onSortChange,
  onBatchDelete,
  onBatchToggle,
  onNavigateToMatch,
}: EntryListProps) {
  const { t } = useTranslation();
  const { currentEntryId, searchQuery, setSearchQuery, currentWorldInfoId } = useWorldInfoStore();
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [contextMenuEntryId, setContextMenuEntryId] = useState<string | null>(null);
  const [isMultiSelect, setIsMultiSelect] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchExpanded, setSearchExpanded] = useState(false);
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null);
  const [dragState, setDragState] = useState<{
    activeIndex: number;
    targetIndex: number;
  } | null>(null);
  const [dropPending, setDropPending] = useState<{
    entryId: string;
    targetIndex: number;
    dy: number;
  } | null>(null);
  const [landingEntryId, setLandingEntryId] = useState<string | null>(null);
  const dragTargetIndexRef = useRef<number | null>(null);
  const draggedEntriesRef = useRef<WorldInfoEntryBrief[] | null>(null);
  const lastDragClientYRef = useRef(0);
  const overlayNodeRef = useRef<HTMLDivElement | null>(null);
  const [, startTransition] = useTransition();
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  const autoScrollFrameRef = useRef<number | null>(null);
  const autoScrollSpeedRef = useRef(0);
  const searchContainerRef = useRef<HTMLDivElement | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
  );

  const [localEntries, setLocalEntries] = useState<WorldInfoEntryBrief[] | null>(null);

  const sortedEntries = useMemo(() => {
    const result = [...(localEntries ?? entries)].sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "order":
          comparison = a.order - b.order;
          break;
        case "uid":
          comparison = a.uid - b.uid;
          break;
        case "tokenCount":
          comparison = a.tokenCount - b.tokenCount;
          break;
        case "name":
          comparison = a.name.localeCompare(b.name, "zh-CN");
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });

    return result;
  }, [entries, localEntries, sortField, sortDirection]);

  // 查询数据更新后，放弃本地重排覆盖，回到查询数据
  useEffect(() => {
    setLocalEntries(null);
  }, [entries]);

  const activeEntry = useMemo(
    () => draggedEntriesRef.current?.find((entry) => entry.id === activeEntryId) ?? null,
    [activeEntryId],
  );

  const updateDragTargetIndex = useCallback((targetIndex: number) => {
    if (dragTargetIndexRef.current === targetIndex) return;

    dragTargetIndexRef.current = targetIndex;
    setDragState((current) => {
      if (!current || current.targetIndex === targetIndex) return current;
      return { ...current, targetIndex };
    });
  }, []);

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(e.target.value);
      if (e.target.value.trim()) {
        setSearchOpen(true);
      }
    },
    [setSearchQuery],
  );

  const handleSearchToggle = useCallback(() => {
    setSearchExpanded((prev) => {
      if (prev) {
        setSearchOpen(false);
        return false;
      }
      return true;
    });
    if (!searchExpanded && searchQuery.trim()) {
      setSearchOpen(true);
    }
  }, [searchExpanded, searchQuery]);

  const handleSearchFocus = useCallback(() => {
    if (searchQuery.trim()) {
      setSearchOpen(true);
    }
  }, [searchQuery]);

  const handleSearchBlur = useCallback(() => {
    if (!searchQuery.trim()) {
      setSearchExpanded(false);
    }
  }, [searchQuery]);

  const handlePopoverOpenChange = useCallback((open: boolean) => {
    setSearchOpen(open);
    if (!open) {
      setSearchExpanded(false);
    }
  }, []);

  useEffect(() => {
    if (searchExpanded && searchContainerRef.current) {
      const input = searchContainerRef.current.querySelector("input");
      input?.focus();
    }
  }, [searchExpanded]);

  const shouldShowDragHandle = useMemo(() => {
    return !isMultiSelect && sortField === "order" && sortDirection === "asc";
  }, [isMultiSelect, sortDirection, sortField]);

  const handleContextMenu = useCallback((entryId: string, position: ContextMenuPosition) => {
    setContextMenuPos(position);
    setContextMenuEntryId(entryId);
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuEntryId(null);
  }, []);

  const handleLongPressStart = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuEntryId(null);
  }, []);

  const handleToggleMultiSelect = useCallback(() => {
    startTransition(() => {
      setIsMultiSelect((prev) => {
        if (prev) {
          setSelectedIds(new Set());
        }
        return !prev;
      });
    });
  }, [startTransition]);

  const handleCheckEntry = useCallback((entryId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(entryId)) {
        next.delete(entryId);
      } else {
        next.add(entryId);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedIds(new Set(sortedEntries.map((e) => e.id)));
  }, [sortedEntries]);

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleBatchDeleteClick = useCallback(() => {
    if (selectedIds.size === 0) return;
    setBatchDeleteDialogOpen(true);
  }, [selectedIds]);

  const handleBatchDeleteConfirm = useCallback(() => {
    if (selectedIds.size === 0) return;
    onBatchDelete(Array.from(selectedIds));
    setSelectedIds(new Set());
    setIsMultiSelect(false);
    setBatchDeleteDialogOpen(false);
  }, [selectedIds, onBatchDelete]);

  const handleBatchEnable = useCallback(() => {
    onBatchToggle(Array.from(selectedIds), true);
  }, [selectedIds, onBatchToggle]);

  const handleBatchDisable = useCallback(() => {
    onBatchToggle(Array.from(selectedIds), false);
  }, [selectedIds, onBatchToggle]);

  const contextMenuEntry = useMemo(
    () => entries.find((entry) => entry.id === contextMenuEntryId) ?? null,
    [entries, contextMenuEntryId],
  );

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    if (isMultiSelect) {
      return [
        {
          id: "enable",
          label: t("worldInfo.batchEnableSelected"),
          icon: ToggleRight,
          onClick: handleBatchEnable,
        },
        {
          id: "disable",
          label: t("worldInfo.batchDisableSelected"),
          icon: ToggleLeft,
          onClick: handleBatchDisable,
        },
        {
          id: "delete",
          label: t("worldInfo.batchDeleteSelected"),
          icon: Trash2,
          danger: true,
          onClick: handleBatchDeleteClick,
        },
      ];
    }

    if (!contextMenuEntry) return [];

    return [
      {
        id: "pin",
        label: t("worldInfo.pinEntry"),
        icon: Pin,
        onClick: () => onPinEntry(contextMenuEntry),
      },
      {
        id: "delete",
        label: t("common.delete"),
        icon: Trash2,
        danger: true,
        onClick: () => onDeleteEntry(contextMenuEntry),
      },
    ];
  }, [
    isMultiSelect,
    contextMenuEntry,
    onDeleteEntry,
    onPinEntry,
    t,
    handleBatchEnable,
    handleBatchDisable,
    handleBatchDeleteClick,
  ]);

  const stopAutoScroll = useCallback(() => {
    autoScrollSpeedRef.current = 0;
    if (autoScrollFrameRef.current !== null) {
      cancelAnimationFrame(autoScrollFrameRef.current);
      autoScrollFrameRef.current = null;
    }
  }, []);

  const clearDragState = useCallback(() => {
    setActiveEntryId(null);
    dragTargetIndexRef.current = null;
    draggedEntriesRef.current = null;
    setDragState(null);
    setDropPending(null);
    setLandingEntryId(null);
  }, []);

  const startAutoScroll = useCallback(() => {
    if (autoScrollFrameRef.current !== null) return;

    const step = () => {
      autoScrollFrameRef.current = null;
      const scrollContainer = scrollContainerRef.current;
      const speed = autoScrollSpeedRef.current;
      if (!scrollContainer || speed === 0) return;

      const nextScrollTop = scrollContainer.scrollTop + speed;
      const maxScrollTop = scrollContainer.scrollHeight - scrollContainer.clientHeight;
      const clampedScrollTop = Math.max(0, Math.min(nextScrollTop, maxScrollTop));
      if (clampedScrollTop === scrollContainer.scrollTop) {
        autoScrollSpeedRef.current = 0;
        return;
      }

      scrollContainer.scrollTop = clampedScrollTop;
      updateDragTargetIndex(
        getDragTargetIndex({
          containerTop: scrollContainer.getBoundingClientRect().top,
          scrollTop: clampedScrollTop,
          clientY: lastDragClientYRef.current,
          itemCount: draggedEntriesRef.current?.length ?? sortedEntries.length,
        }),
      );
      autoScrollFrameRef.current = requestAnimationFrame(step);
    };

    autoScrollFrameRef.current = requestAnimationFrame(step);
  }, [sortedEntries.length, updateDragTargetIndex]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      stopAutoScroll();
      const { active } = event;
      const draggedEntries = draggedEntriesRef.current;
      const newIndex = dragTargetIndexRef.current;
      if (!shouldShowDragHandle || !draggedEntries || newIndex === null) {
        clearDragState();
        return;
      }

      const reordered = reorderEntries(draggedEntries, String(active.id), newIndex);
      if (!reordered) {
        clearDragState();
        return;
      }

      const scrollContainer = scrollContainerRef.current;
      const slotTop = scrollContainer
        ? scrollContainer.getBoundingClientRect().top +
          newIndex * ENTRY_LIST_ITEM_HEIGHT -
          scrollContainer.scrollTop
        : undefined;
      const pointerTop = lastDragClientYRef.current - ENTRY_LIST_ITEM_HEIGHT / 2;
      const dy = slotTop != null ? pointerTop - slotTop : 0;

      flushSync(() => {
        setDragState(null);
        setLocalEntries(reordered);
        onReorderEntries(reordered);
      });

      // 保持源项隐藏，直到 Virtuoso 应用重排后再在目标槽位揭示并滑入
      setDropPending({ entryId: String(active.id), targetIndex: newIndex, dy });

      if (onSaveDragOrder) {
        void Promise.resolve(onSaveDragOrder(String(active.id), newIndex + 1)).catch((error) => {
          console.error("Failed to save drag order:", error);
        });
      }
    },
    [clearDragState, onReorderEntries, onSaveDragOrder, shouldShowDragHandle, stopAutoScroll],
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      stopAutoScroll();
      clearDragState();
      setActiveEntryId(String(event.active.id));
      draggedEntriesRef.current = sortedEntries;
      const activeIndex = sortedEntries.findIndex((entry) => entry.id === event.active.id);
      dragTargetIndexRef.current = activeIndex;
      setDragState({ activeIndex, targetIndex: activeIndex });
      lastDragClientYRef.current = event.active.rect.current.initial?.top ?? 0;
    },
    [clearDragState, sortedEntries, stopAutoScroll],
  );

  const handleDragCancel = useCallback(() => {
    stopAutoScroll();
    clearDragState();
  }, [clearDragState, stopAutoScroll]);

  const handleKeyboardReorder = useCallback(
    (entryId: string, direction: -1 | 1) => {
      if (!shouldShowDragHandle) return;

      const currentIndex = sortedEntries.findIndex((entry) => entry.id === entryId);
      const newIndex = Math.max(0, Math.min(sortedEntries.length - 1, currentIndex + direction));
      const reordered = reorderEntries(sortedEntries, entryId, newIndex);
      if (!reordered) return;

      onReorderEntries(reordered);
      if (onSaveDragOrder) {
        void Promise.resolve(
          onSaveDragOrder(entryId, reordered[newIndex]?.order ?? newIndex + 1),
        ).catch((error) => {
          console.error("Failed to save keyboard order:", error);
        });
      }
    },
    [onReorderEntries, onSaveDragOrder, shouldShowDragHandle, sortedEntries],
  );

  const handleDragMove = useCallback(
    (event: DragMoveEvent) => {
      if (!shouldShowDragHandle) {
        stopAutoScroll();
        return;
      }

      const scrollContainer = scrollContainerRef.current;
      const translatedRect = event.active.rect.current.translated;

      if (!scrollContainer || !translatedRect) {
        stopAutoScroll();
        return;
      }

      const containerRect = scrollContainer.getBoundingClientRect();
      lastDragClientYRef.current = translatedRect.top + translatedRect.height / 2;
      updateDragTargetIndex(
        getDragTargetIndex({
          containerTop: containerRect.top,
          scrollTop: scrollContainer.scrollTop,
          clientY: lastDragClientYRef.current,
          itemCount: draggedEntriesRef.current?.length ?? sortedEntries.length,
        }),
      );
      const speed = getAutoScrollSpeed({
        containerTop: containerRect.top,
        containerBottom: containerRect.bottom,
        itemTop: translatedRect.top,
        itemBottom: translatedRect.bottom,
      });
      autoScrollSpeedRef.current = speed;
      if (speed === 0) {
        stopAutoScroll();
        return;
      }
      startAutoScroll();
    },
    [
      shouldShowDragHandle,
      sortedEntries.length,
      startAutoScroll,
      stopAutoScroll,
      updateDragTargetIndex,
    ],
  );

  useEffect(() => {
    return () => {
      stopAutoScroll();
      clearDragState();
    };
  }, [clearDragState, stopAutoScroll]);

  useEffect(() => {
    if (!dropPending) return;
    const { entryId, dy, targetIndex } = dropPending;
    if (sortedEntries[targetIndex]?.id !== entryId) return;

    setDropPending(null);
    setActiveEntryId(null);
    setLandingEntryId(entryId);
    if (dy !== 0) {
      queueMicrotask(() => {
        flushSync(() => {});
        const el = document.querySelector<HTMLDivElement>(`[data-entry-id="${entryId}"]`);
        el?.animate([{ transform: `translateY(${dy}px)` }, { transform: "translateY(0px)" }], {
          duration: 140,
          easing: "ease",
          fill: "both",
        });
      });
    }
    window.setTimeout(() => setLandingEntryId(null), 180);
  }, [dropPending, sortedEntries]);

  function getSortIcon(field: SortField) {
    if (sortField !== field) return null;
    return sortDirection === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
  }

  return (
    <>
      <Flex
        direction="column"
        height="100%"
        width="100%"
        style={{ minWidth: 0, overflow: "hidden" }}
      >
        <Box
          p="3"
          style={{ borderBottom: "1px solid var(--gray-a5)", flexShrink: 0 }}
        >
          <Flex
            direction="column"
            gap="2"
          >
            <ProjectSelectField
              projects={projects}
              value={currentProjectId}
              onChange={onSelectProject}
              showNoneOption={false}
              placeholder={t("worldInfo.selectProject")}
            />

            <Flex
              gap="2"
              align="center"
            >
              <Box
                ref={searchContainerRef}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0,
                  height: "var(--space-6)",
                  paddingRight: searchExpanded ? "var(--space-2)" : 0,
                  border: "1px solid transparent",
                  borderColor: searchExpanded ? "var(--gray-a7)" : "transparent",
                  borderRadius: "max(var(--radius-2), var(--radius-full))",
                  background: searchExpanded ? "var(--color-surface)" : "transparent",
                  flex: searchExpanded ? 1 : undefined,
                  minWidth: 0,
                  position: "relative",
                  transition:
                    "border-color 0.15s ease, background 0.15s ease, padding-right 0.15s ease",
                }}
              >
                <EntrySearchPopover
                  worldInfoId={currentWorldInfoId ?? ""}
                  query={searchQuery}
                  open={searchOpen}
                  onOpenChange={handlePopoverOpenChange}
                  onNavigateToMatch={onNavigateToMatch}
                >
                  <Box
                    style={{
                      position: "absolute",
                      inset: 0,
                      pointerEvents: "none",
                    }}
                  />
                </EntrySearchPopover>
                <IconButton
                  variant="ghost"
                  size="2"
                  onClick={searchExpanded ? undefined : handleSearchToggle}
                  style={{
                    flexShrink: 0,
                    opacity: searchExpanded ? 0.5 : 1,
                    transition: "opacity 0.15s ease",
                    cursor: searchExpanded ? "default" : undefined,
                  }}
                >
                  <Search size={16} />
                </IconButton>
                <motion.div
                  animate={{ width: searchExpanded ? 200 : 0, opacity: searchExpanded ? 1 : 0 }}
                  transition={{ duration: 0.15, ease: "easeOut" }}
                  style={{ overflow: "hidden" }}
                >
                  <input
                    type="text"
                    placeholder={t("worldInfo.searchPlaceholder")}
                    value={searchQuery}
                    onChange={handleSearchChange}
                    onFocus={handleSearchFocus}
                    onBlur={handleSearchBlur}
                    style={{
                      width: 200,
                      border: "none",
                      outline: "none",
                      background: "transparent",
                      fontSize: "var(--font-size-base)",
                      lineHeight: "var(--line-height-2)",
                      color: "var(--gray-12)",
                      padding: 0,
                    }}
                  />
                </motion.div>
              </Box>

              {!searchExpanded && (
                <>
                  <Box style={{ flex: 1 }} />

                  <Tooltip content={t("common.import")}>
                    <IconButton
                      variant="ghost"
                      size="2"
                      aria-label={t("common.import")}
                      onClick={onImport}
                    >
                      <Upload size={16} />
                    </IconButton>
                  </Tooltip>

                  <DropdownMenu.Root>
                    <DropdownMenu.Trigger>
                      <IconButton
                        variant="ghost"
                        size="2"
                        aria-label={t("worldInfo.sort")}
                      >
                        <ArrowUpDown size={16} />
                      </IconButton>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Content align="end">
                      <DropdownMenu.Item onClick={() => onSortChange("order")}>
                        <Flex
                          align="center"
                          justify="between"
                          width="100%"
                        >
                          <Text>{t("worldInfo.sortByOrder")}</Text>
                          {getSortIcon("order")}
                        </Flex>
                      </DropdownMenu.Item>
                      <DropdownMenu.Item onClick={() => onSortChange("uid")}>
                        <Flex
                          align="center"
                          justify="between"
                          width="100%"
                        >
                          <Text>{t("worldInfo.sortByUid")}</Text>
                          {getSortIcon("uid")}
                        </Flex>
                      </DropdownMenu.Item>
                      <DropdownMenu.Item onClick={() => onSortChange("tokenCount")}>
                        <Flex
                          align="center"
                          justify="between"
                          width="100%"
                        >
                          <Text>{t("worldInfo.sortByTokens")}</Text>
                          {getSortIcon("tokenCount")}
                        </Flex>
                      </DropdownMenu.Item>
                      <DropdownMenu.Item onClick={() => onSortChange("name")}>
                        <Flex
                          align="center"
                          justify="between"
                          width="100%"
                        >
                          <Text>{t("worldInfo.sortByName")}</Text>
                          {getSortIcon("name")}
                        </Flex>
                      </DropdownMenu.Item>
                    </DropdownMenu.Content>
                  </DropdownMenu.Root>

                  {isMultiSelect ? (
                    <Tooltip
                      content={
                        selectedIds.size > 0 ? t("worldInfo.deselectAll") : t("worldInfo.selectAll")
                      }
                    >
                      <IconButton
                        variant="ghost"
                        size="2"
                        onClick={selectedIds.size > 0 ? handleDeselectAll : handleSelectAll}
                      >
                        <CheckSquare size={16} />
                      </IconButton>
                    </Tooltip>
                  ) : null}

                  <Tooltip
                    content={
                      isMultiSelect
                        ? t("worldInfo.multiselectExit")
                        : t("worldInfo.multiselectEnter")
                    }
                  >
                    <IconButton
                      variant={isMultiSelect ? "solid" : "ghost"}
                      size="2"
                      onClick={handleToggleMultiSelect}
                    >
                      <ListChecks size={16} />
                    </IconButton>
                  </Tooltip>
                </>
              )}
            </Flex>

            {isMultiSelect ? (
              <Tooltip content={t("worldInfo.deleteSelectedTooltip")}>
                <IconButton
                  size="2"
                  variant="solid"
                  color="red"
                  disabled={selectedIds.size === 0}
                  onClick={handleBatchDeleteClick}
                  style={{ width: "100%" }}
                >
                  <Trash2 size={16} />
                  <Text
                    size="2"
                    ml="1"
                  >
                    {t("worldInfo.deleteSelected")}
                  </Text>
                </IconButton>
              </Tooltip>
            ) : (
              <Tooltip content={t("worldInfo.newEntry")}>
                <IconButton
                  size="2"
                  variant="soft"
                  onClick={onCreateEntry}
                  style={{ width: "100%" }}
                >
                  <Plus size={16} />
                  <Text
                    size="2"
                    ml="1"
                  >
                    {t("worldInfo.newEntry")}
                  </Text>
                </IconButton>
              </Tooltip>
            )}
          </Flex>
        </Box>

        {isLoading ? (
          <Flex
            direction="column"
            style={{ flex: 1 }}
            gap="0"
          >
            {Array.from({ length: 8 }).map((_, i) => (
              <Box
                key={i}
                p="3"
                style={{ borderBottom: "1px solid var(--gray-a5)" }}
              >
                <Flex
                  align="center"
                  gap="2"
                  justify="between"
                >
                  <Box style={{ width: 16, flexShrink: 0 }}>
                    <Skeleton
                      width="16px"
                      height="16px"
                    />
                  </Box>
                  <Flex
                    direction="column"
                    gap="1"
                    style={{ flex: 1, minWidth: 0 }}
                  >
                    <Skeleton
                      height="14px"
                      width={`${50 + (i % 4) * 12}%`}
                      style={{ maxWidth: 200 }}
                    />
                    <Skeleton
                      height="12px"
                      width="48px"
                    />
                  </Flex>
                  <Skeleton
                    width="28px"
                    height="16px"
                    style={{ borderRadius: 999 }}
                  />
                </Flex>
              </Box>
            ))}
          </Flex>
        ) : sortedEntries.length === 0 ? (
          <Flex
            direction="column"
            align="center"
            justify="center"
            style={{ flex: 1 }}
            py="6"
            gap="2"
          >
            <Text
              size="2"
              color="gray"
            >
              {searchQuery.trim() ? t("worldInfo.noEntriesFound") : t("worldInfo.noEntries")}
            </Text>
          </Flex>
        ) : (
          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragMove={handleDragMove}
            onDragEnd={handleDragEnd}
            onDragCancel={handleDragCancel}
            modifiers={[restrictToVerticalAxis]}
            autoScroll={false}
          >
            <Virtuoso
              data={sortedEntries}
              computeItemKey={(_, entry) => entry.id}
              fixedItemHeight={ENTRY_LIST_ITEM_HEIGHT}
              overscan={VIRTUAL_LIST_OVERSCAN}
              scrollerRef={(element) => {
                scrollContainerRef.current = element instanceof HTMLElement ? element : null;
              }}
              style={{
                flex: 1,
                width: "100%",
                minWidth: 0,
                overscrollBehavior: "contain",
                WebkitOverflowScrolling: "touch",
              }}
              itemContent={(index, entry) => {
                const projectionOffset = dragState
                  ? getEntryDragOffset({
                      entryIndex: index,
                      activeIndex: dragState.activeIndex,
                      targetIndex: dragState.targetIndex,
                    })
                  : 0;
                return (
                  <EntryListItem
                    key={entry.id}
                    entry={entry}
                    isSelected={currentEntryId === entry.id}
                    showDragHandle={shouldShowDragHandle}
                    isMultiSelect={isMultiSelect}
                    isChecked={selectedIds.has(entry.id)}
                    isDragSource={activeEntryId === entry.id}
                    isDragActive={dragState !== null}
                    isLanding={landingEntryId === entry.id}
                    dragOffset={projectionOffset}
                    onCheckChange={handleCheckEntry}
                    onClick={onSelectEntry}
                    onToggle={onToggleEntry}
                    onKeyboardReorder={handleKeyboardReorder}
                    onLongPressStart={handleLongPressStart}
                    onContextMenu={handleContextMenu}
                  />
                );
              }}
            />
            <DragOverlay dropAnimation={null}>
              {activeEntry ? (
                <Box
                  ref={overlayNodeRef}
                  style={{ width: scrollContainerRef.current?.clientWidth }}
                >
                  <EntryListItem
                    entry={activeEntry}
                    isSelected={currentEntryId === activeEntry.id}
                    showDragHandle
                    isDragOverlay
                    onClick={() => undefined}
                    onToggle={() => undefined}
                    onKeyboardReorder={() => undefined}
                    onLongPressStart={() => undefined}
                    onContextMenu={() => undefined}
                  />
                </Box>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </Flex>

      <ContextMenu
        position={contextMenuPos}
        items={menuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root
        open={batchDeleteDialogOpen}
        onOpenChange={setBatchDeleteDialogOpen}
      >
        <Dialog.Content style={{ maxWidth: 400 }}>
          <Dialog.Title>{t("worldInfo.deleteSelected")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mb="4"
          >
            {t("worldInfo.batchDeleteConfirm", { count: selectedIds.size })}
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
              onClick={handleBatchDeleteConfirm}
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </>
  );
}
