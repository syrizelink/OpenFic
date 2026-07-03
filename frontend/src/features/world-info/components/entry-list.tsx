/**
 * Entry List Component
 *
 * 世界书条目列表组件，包含搜索、排序和重排序功能。
 */

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
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
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragMoveEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { restrictToParentElement, restrictToVerticalAxis } from "@dnd-kit/modifiers";

import { EntryListItem } from "./entry-list-item";
import { EntrySearchPopover } from "./entry-search-popover";
import { useWorldInfoStore } from "../store/use-world-info-store";
import { ContextMenu, type ContextMenuItem } from "@/components/context-menu";
import type { WorldInfoEntryBrief } from "@/lib/world-info.types";

/** 排序字段 */
type SortField = "order" | "uid" | "tokenCount" | "name";
/** 排序方向 */
type SortDirection = "asc" | "desc";

const AUTO_SCROLL_EDGE_THRESHOLD = 56;
const AUTO_SCROLL_MAX_SPEED = 18;

interface EntryListProps {
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
  /** 保存拖拽排序回调 */
  onSaveDragOrder?: (changes: Array<{ id: string; newOrder: number }>) => Promise<void> | void;
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
  const [, startTransition] = useTransition();
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const autoScrollFrameRef = useRef<number | null>(null);
  const autoScrollSpeedRef = useRef(0);
  const searchContainerRef = useRef<HTMLDivElement | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const sortedEntries = useMemo(() => {
    const result = [...entries].sort((a, b) => {
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
  }, [entries, sortField, sortDirection]);

  const entryIds = useMemo(() => sortedEntries.map((entry) => entry.id), [sortedEntries]);

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(e.target.value);
      if (e.target.value.trim()) {
        setSearchOpen(true);
      }
    },
    [setSearchQuery]
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

  const handlePopoverOpenChange = useCallback(
    (open: boolean) => {
      setSearchOpen(open);
      if (!open) {
        setSearchExpanded(false);
      }
    },
    []
  );

  useEffect(() => {
    if (searchExpanded && searchContainerRef.current) {
      const input = searchContainerRef.current.querySelector("input");
      input?.focus();
    }
  }, [searchExpanded]);

  const shouldShowDragHandle = useMemo(() => {
    return !isMultiSelect && sortField === "order";
  }, [isMultiSelect, sortField]);

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
    [entries, contextMenuEntryId]
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
  }, [isMultiSelect, contextMenuEntry, onDeleteEntry, onPinEntry, t, handleBatchEnable, handleBatchDisable, handleBatchDeleteClick]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      autoScrollSpeedRef.current = 0;

      if (!shouldShowDragHandle) return;

      const { active, over } = event;
      if (!over || active.id === over.id) return;

      const oldIndex = sortedEntries.findIndex((entry) => entry.id === active.id);
      const newIndex = sortedEntries.findIndex((entry) => entry.id === over.id);
      if (oldIndex === -1 || newIndex === -1) return;

      const reordered = arrayMove(sortedEntries, oldIndex, newIndex).map((entry, index) => ({
        ...entry,
        order: index + 1,
      }));

      onReorderEntries(reordered);

      if (onSaveDragOrder) {
        const changes = reordered.map((entry) => ({ id: entry.id, newOrder: entry.order }));
        setTimeout(() => {
          const result = onSaveDragOrder(changes);
          if (result instanceof Promise) {
            result.catch((error) => {
              console.error("Failed to save drag order:", error);
            });
          }
        }, 0);
      }
    },
    [onReorderEntries, onSaveDragOrder, shouldShowDragHandle, sortedEntries]
  );

  const handleDragStart = useCallback(() => {
    autoScrollSpeedRef.current = 0;
  }, []);

  const handleDragCancel = useCallback(() => {
    autoScrollSpeedRef.current = 0;
  }, []);

  const handleDragMove = useCallback(
    (event: DragMoveEvent) => {
      if (!shouldShowDragHandle) {
        autoScrollSpeedRef.current = 0;
        return;
      }

      const scrollContainer = scrollContainerRef.current;
      const translatedRect = event.active.rect.current.translated;

      if (!scrollContainer || !translatedRect) {
        autoScrollSpeedRef.current = 0;
        return;
      }

      const containerRect = scrollContainer.getBoundingClientRect();
      const distanceToTop = translatedRect.top - containerRect.top;
      const distanceToBottom = containerRect.bottom - translatedRect.bottom;

      if (distanceToTop < AUTO_SCROLL_EDGE_THRESHOLD) {
        const ratio = (AUTO_SCROLL_EDGE_THRESHOLD - distanceToTop) / AUTO_SCROLL_EDGE_THRESHOLD;
        autoScrollSpeedRef.current = -Math.max(4, Math.round(AUTO_SCROLL_MAX_SPEED * ratio));
        return;
      }

      if (distanceToBottom < AUTO_SCROLL_EDGE_THRESHOLD) {
        const ratio = (AUTO_SCROLL_EDGE_THRESHOLD - distanceToBottom) / AUTO_SCROLL_EDGE_THRESHOLD;
        autoScrollSpeedRef.current = Math.max(4, Math.round(AUTO_SCROLL_MAX_SPEED * ratio));
        return;
      }

      autoScrollSpeedRef.current = 0;
    },
    [shouldShowDragHandle]
  );

  useEffect(() => {
    const step = () => {
      const scrollContainer = scrollContainerRef.current;
      const speed = autoScrollSpeedRef.current;

      if (!scrollContainer || speed === 0) {
        autoScrollFrameRef.current = requestAnimationFrame(step);
        return;
      }

      const nextScrollTop = scrollContainer.scrollTop + speed;
      const maxScrollTop = scrollContainer.scrollHeight - scrollContainer.clientHeight;
      const clampedScrollTop = Math.max(0, Math.min(nextScrollTop, maxScrollTop));

      if (clampedScrollTop === scrollContainer.scrollTop) {
        autoScrollSpeedRef.current = 0;
      } else {
        scrollContainer.scrollTop = clampedScrollTop;
      }

      autoScrollFrameRef.current = requestAnimationFrame(step);
    };

    autoScrollFrameRef.current = requestAnimationFrame(step);

    return () => {
      if (autoScrollFrameRef.current !== null) {
        cancelAnimationFrame(autoScrollFrameRef.current);
      }
    };
  }, []);

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
        <Box p="3" style={{ borderBottom: "1px solid var(--gray-a5)", flexShrink: 0 }}>
          <Flex direction="column" gap="2">
            <Flex gap="2" align="center">
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
                  transition: "border-color 0.15s ease, background 0.15s ease, padding-right 0.15s ease",
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
                      fontSize: "var(--font-size-2)",
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

                  {isMultiSelect ? (
                    <Tooltip content={selectedIds.size > 0 ? t("worldInfo.deselectAll") : t("worldInfo.selectAll")}>
                      <IconButton
                        variant="ghost"
                        size="2"
                        onClick={selectedIds.size > 0 ? handleDeselectAll : handleSelectAll}
                      >
                        <CheckSquare size={16} />
                      </IconButton>
                    </Tooltip>
                  ) : (
                    <DropdownMenu.Root>
                      <DropdownMenu.Trigger>
                        <IconButton variant="ghost" size="2">
                          <ArrowUpDown size={16} />
                        </IconButton>
                      </DropdownMenu.Trigger>
                      <DropdownMenu.Content align="end">
                        <DropdownMenu.Item onClick={() => onSortChange("order")}>
                          <Flex align="center" justify="between" width="100%">
                            <Text>{t("worldInfo.sortByOrder")}</Text>
                            {getSortIcon("order")}
                          </Flex>
                        </DropdownMenu.Item>
                        <DropdownMenu.Item onClick={() => onSortChange("uid")}>
                          <Flex align="center" justify="between" width="100%">
                            <Text>{t("worldInfo.sortByUid")}</Text>
                            {getSortIcon("uid")}
                          </Flex>
                        </DropdownMenu.Item>
                        <DropdownMenu.Item onClick={() => onSortChange("tokenCount")}>
                          <Flex align="center" justify="between" width="100%">
                            <Text>{t("worldInfo.sortByTokens")}</Text>
                            {getSortIcon("tokenCount")}
                          </Flex>
                        </DropdownMenu.Item>
                        <DropdownMenu.Item onClick={() => onSortChange("name")}>
                          <Flex align="center" justify="between" width="100%">
                            <Text>{t("worldInfo.sortByName")}</Text>
                            {getSortIcon("name")}
                          </Flex>
                        </DropdownMenu.Item>
                      </DropdownMenu.Content>
                    </DropdownMenu.Root>
                  )}

                  <Tooltip content={isMultiSelect ? t("worldInfo.multiselectExit") : t("worldInfo.multiselectEnter")}>
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
                  <Text size="2" ml="1">
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
                  <Text size="2" ml="1">
                    {t("worldInfo.newEntry")}
                  </Text>
                </IconButton>
              </Tooltip>
            )}
          </Flex>
        </Box>

        <Box
          ref={scrollContainerRef}
          style={{
            flex: 1,
            width: "100%",
            minWidth: 0,
            overflowY: "auto",
            overflowX: "hidden",
            overscrollBehavior: "contain",
            WebkitOverflowScrolling: "touch",
          }}
        >
          <Box
            style={{
              width: "100%",
              minWidth: 0,
              overflowX: "hidden",
              contain: "layout style",
            }}
          >
            {isLoading ? (
              <Flex direction="column" gap="0">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Box key={i} p="3" style={{ borderBottom: "1px solid var(--gray-a5)" }}>
                    <Flex align="center" gap="2" justify="between">
                      <Box style={{ width: 16, flexShrink: 0 }}>
                        <Skeleton width="16px" height="16px" />
                      </Box>
                      <Flex direction="column" gap="1" style={{ flex: 1, minWidth: 0 }}>
                        <Skeleton
                          height="14px"
                          width={`${50 + (i % 4) * 12}%`}
                          style={{ maxWidth: 200 }}
                        />
                        <Skeleton height="12px" width="48px" />
                      </Flex>
                      <Skeleton width="28px" height="16px" style={{ borderRadius: 999 }} />
                    </Flex>
                  </Box>
                ))}
              </Flex>
            ) : sortedEntries.length === 0 ? (
              <Flex direction="column" align="center" justify="center" py="6" gap="2">
                <Text size="2" color="gray">
                  {searchQuery.trim() ? t("worldInfo.noEntriesFound") : t("worldInfo.noEntries")}
                </Text>
              </Flex>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={handleDragEnd}
                onDragCancel={handleDragCancel}
                modifiers={[restrictToVerticalAxis, restrictToParentElement]}
                autoScroll={false}
              >
                <SortableContext
                  items={entryIds}
                  strategy={verticalListSortingStrategy}
                  disabled={!shouldShowDragHandle}
                >
                  <Flex direction="column" width="100%" style={{ minWidth: 0 }}>
                    {sortedEntries.map((entry) => (
                        <EntryListItem
                          key={entry.id}
                          entry={entry}
                          isSelected={currentEntryId === entry.id}
                          showDragHandle={shouldShowDragHandle}
                          isMultiSelect={isMultiSelect}
                          isChecked={selectedIds.has(entry.id)}
                          onCheckChange={handleCheckEntry}
                          onClick={onSelectEntry}
                          onToggle={onToggleEntry}
                          onLongPressStart={handleLongPressStart}
                          onContextMenu={handleContextMenu}
                        />
                    ))}
                  </Flex>
                </SortableContext>
              </DndContext>
            )}
          </Box>
        </Box>
      </Flex>

      <ContextMenu
        position={contextMenuPos}
        items={menuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root open={batchDeleteDialogOpen} onOpenChange={setBatchDeleteDialogOpen}>
        <Dialog.Content style={{ maxWidth: 400 }}>
          <Dialog.Title>{t("worldInfo.deleteSelected")}</Dialog.Title>
          <Dialog.Description size="2" mb="4">
            {t("worldInfo.batchDeleteConfirm", { count: selectedIds.size })}
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
