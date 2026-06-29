/**
 * Chapter List Item
 *
 * 章节列表项组件，显示章节名、字数和编辑时间。
 * 普通滚动路径不接入 dnd-kit，只在拖拽模式下启用 sortable。
 */

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, Flex, Text, Tooltip } from "@radix-ui/themes";
import { GripVertical, MoreHorizontal } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { formatRelativeTime } from "@/lib/time-utils";
import type { ChapterListItem as ChapterListItemType } from "@/lib/chapter.types";
import type { SummaryStatus } from "@/lib/api-client";
import { SummaryStatusDot } from "./summary-status-dot";

function RenameInput({
  initialValue,
  onConfirm,
  onCancel,
}: {
  initialValue: string;
  onConfirm: (newTitle: string) => void;
  onCancel: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmedValue = value.trim();
    if (trimmedValue && trimmedValue !== initialValue) {
      onConfirm(trimmedValue);
      return;
    }
    onCancel();
  }, [initialValue, onCancel, onConfirm, value]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleSubmit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    },
    [handleSubmit, onCancel]
  );

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={handleSubmit}
      onKeyDown={handleKeyDown}
      onClick={(event) => event.stopPropagation()}
      style={{
        width: "100%",
        height: "20px",
        padding: 0,
        margin: 0,
        border: "none",
        outline: "none",
        background: "transparent",
        fontFamily: "inherit",
        fontSize: "14px",
        fontWeight: 500,
        lineHeight: "20px",
        color: "var(--gray-12)",
        boxSizing: "border-box",
      }}
    />
  );
}

interface ChapterListItemBaseProps {
  chapter: ChapterListItemType;
  isActive: boolean;
  isRenaming?: boolean;
  onSelectChapter: (chapterId: string) => void;
  onLongPressStart?: () => void;
  onRequestContextMenu?: (
    chapterId: string,
    chapterTitle: string,
    position: { x: number; y: number }
  ) => void;
  isMenuOpen?: boolean;
  onRenameChapter?: (chapterId: string, newTitle: string) => void;
  onRenameCancel?: () => void;
  summaryStatus?: SummaryStatus;
  summaryIsStale?: boolean;
}

interface ChapterRowContentProps {
  chapter: ChapterListItemType;
  isRenaming: boolean;
  onRenameConfirm?: (newTitle: string) => void;
  onRenameCancel?: () => void;
  summaryStatus?: SummaryStatus;
  summaryIsStale: boolean;
  isMenuButtonVisible?: boolean;
  onOpenMenu?: (triggerElement: HTMLElement) => void;
  textColor?: string;
  dragHandle?: React.ReactNode;
}

function ChapterRowContent({
  chapter,
  isRenaming,
  onRenameConfirm,
  onRenameCancel,
  summaryStatus,
  summaryIsStale,
  isMenuButtonVisible = false,
  onOpenMenu,
  textColor,
  dragHandle,
}: ChapterRowContentProps) {
  const { t } = useTranslation();
  const showMenuTrigger = Boolean(onOpenMenu);

  return (
    <Flex gap="2" align="center" style={{ minWidth: 0, padding: "12px 18px" }}>
      {dragHandle}

      <Box style={{ flex: 1, minWidth: 0 }}>
        {isRenaming && onRenameConfirm && onRenameCancel ? (
          <Box style={{ height: "20px" }}>
            <RenameInput
              key={chapter.id}
              initialValue={chapter.title}
              onConfirm={onRenameConfirm}
              onCancel={onRenameCancel}
            />
          </Box>
        ) : (
          <Text
            size="2"
            weight="medium"
            style={{
              display: "block",
              height: "20px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: textColor,
              userSelect: "none",
              WebkitUserSelect: "none",
            }}
          >
            {chapter.title || t("writing.untitledChapter")}
          </Text>
        )}

        <Flex gap="2" mt="1">
          <Text size="1" color={textColor ? undefined : "gray"} style={{ color: textColor }}>
            {chapter.wordCount} {t("writing.words")}
          </Text>
          <Text size="1" color={textColor ? undefined : "gray"} style={{ color: textColor }}>
            · {formatRelativeTime(chapter.updatedAt)}
          </Text>
        </Flex>
      </Box>

      {showMenuTrigger ? (
        <Flex align="center" gap="4" style={{ flexShrink: 0 }}>
          <Tooltip content={t("chapterMenu.moreActions")}>
            <button
              type="button"
              aria-label={t("chapterMenu.moreActions")}
              tabIndex={isMenuButtonVisible ? 0 : -1}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onOpenMenu?.(event.currentTarget);
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 20,
                height: 20,
                padding: 0,
                border: "none",
                borderRadius: 6,
                background: "transparent",
                color: textColor ?? "var(--gray-10)",
                opacity: isMenuButtonVisible ? 1 : 0,
                pointerEvents: isMenuButtonVisible ? "auto" : "none",
                transform: isMenuButtonVisible ? "scale(1)" : "scale(0.72)",
                transformOrigin: "center",
                transition: "opacity 0.16s ease, transform 0.16s ease, color 0.16s ease",
                cursor: "pointer",
              }}
            >
              <MoreHorizontal size={14} />
            </button>
          </Tooltip>
          <SummaryStatusDot status={summaryStatus} isStale={summaryIsStale} />
        </Flex>
      ) : (
        <SummaryStatusDot status={summaryStatus} isStale={summaryIsStale} />
      )}
    </Flex>
  );
}

function ChapterListItemComponent({
  chapter,
  isActive,
  isRenaming = false,
  onSelectChapter,
  onLongPressStart,
  onRequestContextMenu,
  isMenuOpen = false,
  onRenameChapter,
  onRenameCancel,
  summaryStatus,
  summaryIsStale = false,
}: ChapterListItemBaseProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isLongPressPending, setIsLongPressPending] = useState(false);
  const [isLongPressActive, setIsLongPressActive] = useState(false);
  const longPressTimeoutRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const longPressPositionRef = useRef<{ x: number; y: number } | null>(null);
  const suppressContextMenuRef = useRef(false);

  const isPressed = isLongPressPending || isLongPressActive;
  const isDarkPressed = isLongPressActive;
  const isPendingPressed = isLongPressPending && !isLongPressActive;
  const textColor = isDarkPressed ? "var(--gray-1)" : undefined;
  const isMenuButtonVisible = Boolean(onRequestContextMenu) && !isRenaming && (isHovered || isMenuOpen);

  const style = useMemo(
    () => ({
      opacity: isPressed ? 0.5 : 1,
      background: isDarkPressed
        ? "var(--gray-12)"
        : isPendingPressed
          ? "var(--gray-a6)"
          : isActive
            ? "var(--accent-a3)"
            : "transparent",
      cursor: "pointer",
      width: "100%",
      minWidth: 0,
      overflow: "hidden",
      position: "relative" as const,
      contain: "layout style" as const,
      touchAction: "pan-y",
      userSelect: "none" as const,
      WebkitUserSelect: "none" as const,
      WebkitTouchCallout: "none" as const,
      WebkitTapHighlightColor: "transparent",
      transition: "background-color 0.08s ease, color 0.08s ease, opacity 0.08s ease",
    }),
    [isActive, isDarkPressed, isPendingPressed, isPressed]
  );

  useEffect(() => {
    if (!isLongPressPending && !isLongPressActive) return;

    const handlePointerUp = () => {
      if (isLongPressActive) {
        const position = longPressPositionRef.current;
        if (position && !isRenaming) {
          longPressTriggeredRef.current = true;
          suppressContextMenuRef.current = true;
          onRequestContextMenu?.(chapter.id, chapter.title, position);
        }
      }

      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
        longPressTimeoutRef.current = null;
      }
      setIsLongPressPending(false);
      setIsLongPressActive(false);
      window.getSelection()?.removeAllRanges();
    };

    const handlePointerCancel = () => {
      setIsLongPressPending(false);
      setIsLongPressActive(false);
      window.getSelection()?.removeAllRanges();
    };

    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerCancel);
    return () => {
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerCancel);
    };
  }, [chapter.id, chapter.title, isLongPressActive, isLongPressPending, isRenaming, onRequestContextMenu]);

  useEffect(
    () => () => {
      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
      }
    },
    []
  );

  const clearLongPress = useCallback(() => {
    if (longPressTimeoutRef.current !== null) {
      window.clearTimeout(longPressTimeoutRef.current);
      longPressTimeoutRef.current = null;
    }
    setIsLongPressPending(false);
  }, []);

  const resetPressState = useCallback(() => {
    clearLongPress();
    setIsLongPressActive(false);
  }, [clearLongPress]);

  const handleRenameConfirm = useCallback(
    (newTitle: string) => {
      onRenameChapter?.(chapter.id, newTitle);
    },
    [chapter.id, onRenameChapter]
  );

  const triggerLongPressMenu = useCallback(() => {
    setIsLongPressPending(false);
    setIsLongPressActive(true);
    suppressContextMenuRef.current = true;
    window.getSelection()?.removeAllRanges();
  }, []);

  const handleContextMenu = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      if (suppressContextMenuRef.current) {
        suppressContextMenuRef.current = false;
        return;
      }

      longPressTriggeredRef.current = false;
      resetPressState();
      onRequestContextMenu?.(chapter.id, chapter.title, {
        x: event.clientX,
        y: event.clientY,
      });
    },
    [chapter.id, chapter.title, onRequestContextMenu, resetPressState]
  );

  const handleOpenMenuFromButton = useCallback(
    (triggerElement: HTMLElement) => {
      if (isRenaming) {
        return;
      }
      const rect = triggerElement.getBoundingClientRect();
      onRequestContextMenu?.(chapter.id, chapter.title, {
        x: rect.right - 4,
        y: rect.bottom + 4,
      });
    },
    [chapter.id, chapter.title, isRenaming, onRequestContextMenu]
  );

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (isRenaming) return;
      if (event.pointerType === "mouse" || event.button !== 0) return;

      onLongPressStart?.();
      window.getSelection()?.removeAllRanges();
      longPressTriggeredRef.current = false;
      setIsLongPressActive(false);
      setIsLongPressPending(true);
      longPressPositionRef.current = { x: event.clientX, y: event.clientY };

      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
      }

      longPressTimeoutRef.current = window.setTimeout(() => {
        longPressTimeoutRef.current = null;
        triggerLongPressMenu();
      }, 280);
    },
    [isRenaming, onLongPressStart, triggerLongPressMenu]
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const position = longPressPositionRef.current;
      if (!position || !isLongPressPending) return;

      if (
        Math.abs(event.clientX - position.x) > 8
        || Math.abs(event.clientY - position.y) > 8
      ) {
        resetPressState();
      }
    },
    [isLongPressPending, resetPressState]
  );

  const handleSelect = useCallback(() => {
    if (longPressTriggeredRef.current) {
      longPressTriggeredRef.current = false;
      return;
    }
    onSelectChapter(chapter.id);
  }, [chapter.id, onSelectChapter]);

  return (
    <Box
      className="chapter-list-item-row"
      style={style}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={isRenaming ? undefined : handleSelect}
      onContextMenu={handleContextMenu}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
    >
      <ChapterRowContent
        chapter={chapter}
        isRenaming={isRenaming}
        onRenameConfirm={handleRenameConfirm}
        onRenameCancel={onRenameCancel}
        summaryStatus={summaryStatus}
        summaryIsStale={summaryIsStale}
        isMenuButtonVisible={isMenuButtonVisible}
        onOpenMenu={onRequestContextMenu ? handleOpenMenuFromButton : undefined}
        textColor={textColor}
      />
    </Box>
  );
}

interface SortableChapterListItemProps {
  chapter: ChapterListItemType;
  isActive: boolean;
  onSelectChapter: (chapterId: string) => void;
  summaryStatus?: SummaryStatus;
  summaryIsStale?: boolean;
}

function SortableChapterListItemComponent({
  chapter,
  isActive,
  onSelectChapter,
  summaryStatus,
  summaryIsStale = false,
}: SortableChapterListItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: chapter.id,
  });

  const style = useMemo(
    () => ({
      transform: CSS.Transform.toString(transform),
      transition: transition
        ? `${transition}, background-color 0.08s ease, opacity 0.08s ease`
        : "background-color 0.08s ease, opacity 0.08s ease",
      opacity: isDragging ? 0.5 : 1,
      background: isDragging
        ? "var(--accent-a2)"
        : isActive
          ? "var(--accent-a3)"
          : "transparent",
      cursor: "grab",
      width: "100%",
      minWidth: 0,
      overflow: "hidden",
      position: "relative" as const,
      contain: "layout style" as const,
      touchAction: isDragging ? "none" : "pan-y",
      userSelect: "none" as const,
      WebkitUserSelect: "none" as const,
      WebkitTouchCallout: "none" as const,
      WebkitTapHighlightColor: "transparent",
    }),
    [isActive, isDragging, transform, transition]
  );

  const handleSelect = useCallback(() => {
    onSelectChapter(chapter.id);
  }, [chapter.id, onSelectChapter]);

  const handleDragHandlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      listeners?.onPointerDown?.(event);
    },
    [listeners]
  );

  return (
    <Box
      ref={setNodeRef}
      className="chapter-list-item-row"
      style={style}
      onClick={handleSelect}
      {...attributes}
    >
      <ChapterRowContent
        chapter={chapter}
        isRenaming={false}
        summaryStatus={summaryStatus}
        summaryIsStale={summaryIsStale}
        dragHandle={(
          <Box
            style={{
              color: "var(--gray-9)",
              flexShrink: 0,
              touchAction: "none",
            }}
            onPointerDown={handleDragHandlePointerDown}
            onClick={(event) => event.stopPropagation()}
          >
            <GripVertical size={16} />
          </Box>
        )}
      />
    </Box>
  );
}

function areBaseRowPropsEqual(
  prev: ChapterListItemBaseProps,
  next: ChapterListItemBaseProps
) {
  return (
    prev.chapter.id === next.chapter.id
    && prev.chapter.title === next.chapter.title
    && prev.chapter.order === next.chapter.order
    && prev.chapter.wordCount === next.chapter.wordCount
    && prev.chapter.updatedAt === next.chapter.updatedAt
    && prev.isActive === next.isActive
    && prev.isRenaming === next.isRenaming
    && prev.isMenuOpen === next.isMenuOpen
    && prev.summaryStatus === next.summaryStatus
    && prev.summaryIsStale === next.summaryIsStale
    && prev.onSelectChapter === next.onSelectChapter
    && prev.onLongPressStart === next.onLongPressStart
    && prev.onRequestContextMenu === next.onRequestContextMenu
    && prev.onRenameChapter === next.onRenameChapter
    && prev.onRenameCancel === next.onRenameCancel
  );
}

function areSortableRowPropsEqual(
  prev: SortableChapterListItemProps,
  next: SortableChapterListItemProps
) {
  return (
    prev.chapter.id === next.chapter.id
    && prev.chapter.title === next.chapter.title
    && prev.chapter.order === next.chapter.order
    && prev.chapter.wordCount === next.chapter.wordCount
    && prev.chapter.updatedAt === next.chapter.updatedAt
    && prev.isActive === next.isActive
    && prev.summaryStatus === next.summaryStatus
    && prev.summaryIsStale === next.summaryIsStale
    && prev.onSelectChapter === next.onSelectChapter
  );
}

export const ChapterListItem = memo(ChapterListItemComponent, areBaseRowPropsEqual);
export const SortableChapterListItem = memo(
  SortableChapterListItemComponent,
  areSortableRowPropsEqual
);
