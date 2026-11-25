import { Box, Flex, IconButton, Tooltip, Badge } from "@radix-ui/themes";
import {
  BookPlus,
  Check,
  Download,
  FilePlus,
  FolderInput,
  GripVertical,
  ListChecks,
  Search,
  Summary,
  Trash2,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";

import "./sidebar-toolbar.css";

import type { ChapterListItem } from "@/lib/chapter.types";

import { useWritingStore } from "../store/use-writing-store";
import { ChapterSearchPopover } from "./chapter-search-popover";

interface SidebarToolbarProps {
  projectId: string;
  chapters: ChapterListItem[];
  onChapterSelect: (chapterId: string) => void;
  onCreateChapter: () => void;
  onCreateVolume: () => void;
  onOpenSummary?: () => void;
  onExport: () => void;
  onSaveOrder: () => void;
  onCancelOrder: () => void;
  isSelectMode: boolean;
  onToggleSelectMode: () => void;
  selectedCount: number;
  isBatchPending: boolean;
  onBatchDelete: () => void;
  onBatchMove: () => void;
  onBatchExport: () => void;
  isSavingOrder?: boolean;
  isAgentLocked?: boolean;
  onLockedAction?: () => void;
}

export function SidebarToolbar({
  projectId,
  chapters,
  onChapterSelect,
  onCreateChapter,
  onCreateVolume,
  onOpenSummary,
  onExport,
  onSaveOrder,
  onCancelOrder,
  isSelectMode,
  onToggleSelectMode,
  selectedCount,
  isBatchPending,
  onBatchDelete,
  onBatchMove,
  onBatchExport,
  isSavingOrder,
  isAgentLocked = false,
  onLockedAction,
}: SidebarToolbarProps) {
  const { t } = useTranslation();
  const { isDragMode, hasUnsavedDragChanges, enterDragMode } = useWritingStore(
    useShallow((state) => ({
      isDragMode: state.isDragMode,
      hasUnsavedDragChanges: state.hasUnsavedDragChanges,
      enterDragMode: state.enterDragMode,
    })),
  );

  const [contentSearchOpen, setContentSearchOpen] = useState(false);
  const [contentSearchExpanded, setContentSearchExpanded] = useState(false);
  const [contentSearchQuery, setContentSearchQuery] = useState("");
  const searchContainerRef = useRef<HTMLDivElement | null>(null);
  const toolbarContentRef = useRef<HTMLDivElement | null>(null);
  const selectModeBadgeRef = useRef<HTMLSpanElement | null>(null);
  const selectedCountBadgeRef = useRef<HTMLSpanElement | null>(null);
  const toolbarActionsRef = useRef<HTMLDivElement | null>(null);
  const [isSelectedCountHidden, setIsSelectedCountHidden] = useState(false);

  useLayoutEffect(() => {
    if (!isSelectMode) return;
    const toolbar = toolbarContentRef.current;
    const modeBadge = selectModeBadgeRef.current;
    const countBadge = selectedCountBadgeRef.current;
    const actions = toolbarActionsRef.current;
    if (!toolbar || !modeBadge || !countBadge || !actions) return;

    const updateVisibility = () => {
      const countMargin = parseFloat(getComputedStyle(countBadge).marginLeft) || 0;
      const requiredWidth =
        modeBadge.getBoundingClientRect().width +
        countBadge.getBoundingClientRect().width +
        countMargin +
        actions.getBoundingClientRect().width;
      setIsSelectedCountHidden(requiredWidth > toolbar.clientWidth);
    };
    const observer = new ResizeObserver(updateVisibility);
    [toolbar, modeBadge, countBadge, actions].forEach((element) => observer.observe(element));
    updateVisibility();
    return () => observer.disconnect();
  }, [isSelectMode, selectedCount, t]);

  const handleEnterDragMode = () => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }
    enterDragMode(chapters.map((chapter) => ({ id: chapter.id, order: chapter.order })));
  };

  const handleCancelDragMode = () => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }
    onCancelOrder();
  };

  const handleSaveCurrentOrder = () => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }
    onSaveOrder();
  };

  const handleCreate = () => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }
    onCreateChapter();
  };

  const handleCreateVolume = () => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }
    onCreateVolume();
  };

  const handleContentSearchToggle = useCallback(() => {
    setContentSearchExpanded((prev) => {
      if (prev) {
        setContentSearchOpen(false);
        return false;
      }
      return true;
    });
    if (!contentSearchExpanded && contentSearchQuery.trim()) {
      setContentSearchOpen(true);
    }
  }, [contentSearchExpanded, contentSearchQuery]);

  const handleContentSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setContentSearchQuery(e.target.value);
    if (e.target.value.trim()) {
      setContentSearchOpen(true);
    }
  }, []);

  const handleContentSearchFocus = useCallback(() => {
    if (contentSearchQuery.trim()) {
      setContentSearchOpen(true);
    }
  }, [contentSearchQuery]);

  const handleContentSearchBlur = useCallback(() => {
    if (!contentSearchQuery.trim()) {
      setContentSearchExpanded(false);
    }
  }, [contentSearchQuery]);

  const handlePopoverOpenChange = useCallback((open: boolean) => {
    setContentSearchOpen(open);
    if (!open) {
      setContentSearchExpanded(false);
    }
  }, []);

  useEffect(() => {
    if (contentSearchExpanded && searchContainerRef.current) {
      const input = searchContainerRef.current.querySelector("input");
      input?.focus();
    }
  }, [contentSearchExpanded]);

  const handleNavigateToChapter = useCallback(
    (chapterId: string) => {
      onChapterSelect(chapterId);
    },
    [onChapterSelect],
  );

  return (
    <Box
      px="3"
      py="2"
      style={{
        borderBottom: "1px solid var(--gray-a4)",
      }}
    >
      <Flex
        ref={toolbarContentRef}
        gap="0"
        align="center"
        justify={contentSearchExpanded ? "start" : "between"}
      >
        <Flex
          gap="0"
          align="center"
          style={contentSearchExpanded ? { flex: 1 } : undefined}
        >
          {!isDragMode && !isSelectMode && (
            <Box
              ref={searchContainerRef}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 0,
                height: "var(--space-6)",
                paddingRight: contentSearchExpanded ? "var(--space-2)" : 0,
                border: "1px solid transparent",
                borderColor: contentSearchExpanded ? "var(--gray-a7)" : "transparent",
                borderRadius: "max(var(--radius-2), var(--radius-full))",
                background: contentSearchExpanded ? "var(--color-background)" : "transparent",
                flex: contentSearchExpanded ? 1 : undefined,
                minWidth: 0,
                position: "relative",
                transition:
                  "border-color 0.15s ease, background 0.15s ease, padding-right 0.15s ease",
              }}
            >
              <ChapterSearchPopover
                projectId={projectId}
                query={contentSearchQuery}
                open={contentSearchOpen}
                onOpenChange={handlePopoverOpenChange}
                onNavigateToChapter={handleNavigateToChapter}
              >
                <Box
                  style={{
                    position: "absolute",
                    inset: 0,
                    pointerEvents: "none",
                  }}
                />
              </ChapterSearchPopover>
              <IconButton
                variant="ghost"
                color="gray"
                highContrast
                size="2"
                onClick={contentSearchExpanded ? undefined : handleContentSearchToggle}
                style={{
                  flexShrink: 0,
                  opacity: contentSearchExpanded ? 0.5 : 1,
                  transition: "opacity 0.15s ease",
                  cursor: contentSearchExpanded ? "default" : undefined,
                }}
              >
                <Search size={16} />
              </IconButton>
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{
                  width: contentSearchExpanded ? "100%" : 0,
                  opacity: contentSearchExpanded ? 1 : 0,
                }}
                transition={{ duration: 0.15, ease: "easeOut" }}
                style={{ overflow: "hidden" }}
              >
                {contentSearchExpanded && (
                  <input
                    type="text"
                    placeholder={t("writing.contentSearchPlaceholder")}
                    value={contentSearchQuery}
                    onChange={handleContentSearchChange}
                    onFocus={handleContentSearchFocus}
                    onBlur={handleContentSearchBlur}
                    style={{
                      width: "100%",
                      border: "none",
                      outline: "none",
                      background: "transparent",
                      fontFamily: "var(--app-font-family)",
                      fontSize: "var(--font-size-base)",
                      lineHeight: "var(--line-height-2)",
                      color: "var(--gray-12)",
                      padding: 0,
                    }}
                  />
                )}
              </motion.div>
            </Box>
          )}

          {!contentSearchExpanded && (
            <>
              {isSelectMode ? (
                <>
                  <Badge
                    ref={selectModeBadgeRef}
                    className="chapter-sidebar-select-mode"
                    color="blue"
                    variant="soft"
                  >
                    {t("writing.selectMode")}
                  </Badge>
                  <Badge
                    ref={selectedCountBadgeRef}
                    className="chapter-sidebar-selected-count"
                    data-hidden={isSelectedCountHidden ? "true" : undefined}
                    color="gray"
                    variant="soft"
                    ml="2"
                    aria-label={t("writing.selectedChapters", { count: selectedCount })}
                  >
                    {t("writing.selectedCount", { count: selectedCount })}
                  </Badge>
                </>
              ) : !isDragMode ? (
                <Tooltip content={t("writing.dragModeOn")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    highContrast
                    size="2"
                    onClick={handleEnterDragMode}
                  >
                    <GripVertical size={16} />
                  </IconButton>
                </Tooltip>
              ) : (
                <Badge
                  color="blue"
                  variant="soft"
                >
                  {t("writing.dragModeOn")}
                </Badge>
              )}
              {!isDragMode && !isSelectMode && (
                <Tooltip content={t("writing.selectMode")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    highContrast
                    size="2"
                    aria-label={t("writing.selectMode")}
                    aria-pressed={false}
                    onClick={onToggleSelectMode}
                  >
                    <ListChecks size={16} />
                  </IconButton>
                </Tooltip>
              )}
            </>
          )}
        </Flex>

        {!contentSearchExpanded && (
          <Flex
            ref={toolbarActionsRef}
            className="chapter-sidebar-toolbar-actions"
            data-select-mode={isSelectMode ? "true" : undefined}
            gap="0"
            align="center"
          >
            {isDragMode ? (
              <>
                <Tooltip content={t("writing.cancelOrder")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    size="2"
                    onClick={handleCancelDragMode}
                    disabled={isSavingOrder}
                  >
                    <X size={16} />
                  </IconButton>
                </Tooltip>

                <Tooltip content={t("writing.saveOrder")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    size="2"
                    onClick={handleSaveCurrentOrder}
                    disabled={!hasUnsavedDragChanges || isSavingOrder}
                  >
                    <Check size={16} />
                  </IconButton>
                </Tooltip>
              </>
            ) : isSelectMode ? (
              <>
                <Tooltip content={t("common.cancel")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    size="2"
                    aria-label={t("common.cancel")}
                    disabled={isBatchPending}
                    onClick={onToggleSelectMode}
                  >
                    <X size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip content={t("writing.batchMove")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    size="2"
                    aria-label={t("writing.batchMove")}
                    disabled={!selectedCount || isBatchPending}
                    onClick={onBatchMove}
                  >
                    <FolderInput size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip content={t("writing.batchExport")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    size="2"
                    aria-label={t("writing.batchExport")}
                    disabled={!selectedCount || isBatchPending}
                    onClick={onBatchExport}
                  >
                    <Download size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip content={t("writing.batchDelete")}>
                  <IconButton
                    variant="ghost"
                    color="red"
                    size="2"
                    aria-label={t("writing.batchDelete")}
                    disabled={!selectedCount || isBatchPending}
                    onClick={onBatchDelete}
                  >
                    <Trash2 size={16} />
                  </IconButton>
                </Tooltip>
              </>
            ) : (
              <>
                <Tooltip content={t("writing.newChapter")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    highContrast
                    size="2"
                    onClick={handleCreate}
                  >
                    <FilePlus size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip content={t("writing.newVolume")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    highContrast
                    size="2"
                    onClick={handleCreateVolume}
                  >
                    <BookPlus size={16} />
                  </IconButton>
                </Tooltip>
                {onOpenSummary && (
                  <Tooltip content={t("summary.openPanel")}>
                    <IconButton
                      variant="ghost"
                      color="gray"
                      highContrast
                      size="2"
                      aria-label={t("summary.openPanel")}
                      onClick={onOpenSummary}
                    >
                      <Summary size={16} />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip content={t("writing.chapterExport.open")}>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    highContrast
                    size="2"
                    onClick={onExport}
                  >
                    <Download size={16} />
                  </IconButton>
                </Tooltip>
              </>
            )}
          </Flex>
        )}
      </Flex>
    </Box>
  );
}
