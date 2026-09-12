/**
 * Entry List Item Component
 *
 * Komponen item daftar entri buku dunia, mendukung pengurutan tarik-lepas.
 */

import { useDraggable } from "@dnd-kit/core";
import { Box, Flex, Text, Switch, Checkbox } from "@radix-ui/themes";
import { GripVertical } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatRelativeTime } from "@/lib/time-utils";
import type { WorldInfoEntryBrief } from "@/lib/world-info.types";

import {
  ENTRY_LIST_ITEM_HEIGHT,
  getEntryListTransition,
  shouldHideDraggedEntry,
} from "./entry-list-drag";

interface EntryListItemProps {
  /** Data entri */
  entry: WorldInfoEntryBrief;
  /** Status terpilih */
  isSelected: boolean;
  /** Status tampil pegangan tarik-lepas */
  showDragHandle: boolean;
  /** Status mode pilih ganda */
  isMultiSelect?: boolean;
  /** Status tercentang kotak centang */
  isChecked?: boolean;
  /** Menandai item ini sebagai sumber tarik-lepas saat ini */
  isDragSource?: boolean;
  /** Status aktif proyeksi tarik-lepas */
  isDragActive?: boolean;
  /** Menandai sedang meluncur ke posisi akhir */
  isLanding?: boolean;
  /** Pergeseran item daftar saat ditarik */
  dragOffset?: number;
  /** Menandai dirender sebagai lapisan penutup tarik-lepas */
  isDragOverlay?: boolean;
  /** Callback perubahan status kotak centang */
  onCheckChange?: (entryId: string) => void;
  /** Callback klik */
  onClick: (entryId: string) => void;
  /** Callback pengalihan status aktif */
  onToggle: (entryId: string) => void;
  /** Callback awal tekan lama */
  onLongPressStart: () => void;
  /** Callback menu klik kanan */
  onContextMenu: (entryId: string, position: { x: number; y: number }) => void;
  /** Menyesuaikan urutan lewat papan tombol */
  onKeyboardReorder: (entryId: string, direction: -1 | 1) => void;
}

function EntryListItemComponent({
  entry,
  isSelected,
  showDragHandle,
  isMultiSelect = false,
  isChecked = false,
  isDragSource = false,
  isDragActive = false,
  isLanding = false,
  dragOffset = 0,
  isDragOverlay = false,
  onCheckChange,
  onClick,
  onToggle,
  onLongPressStart,
  onContextMenu,
  onKeyboardReorder,
}: EntryListItemProps) {
  const { t } = useTranslation();
  const [isHandlePressed, setIsHandlePressed] = useState(false);
  const [isLongPressPending, setIsLongPressPending] = useState(false);
  const [isLongPressActive, setIsLongPressActive] = useState(false);
  const longPressTimeoutRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const longPressPositionRef = useRef<{ x: number; y: number } | null>(null);
  const suppressContextMenuRef = useRef(false);

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: entry.id,
    disabled: !showDragHandle || isDragOverlay,
  });

  const setCombinedRef = useCallback(
    (node: HTMLDivElement | null) => {
      setNodeRef(node);
    },
    [setNodeRef],
  );

  const isContentPressed = isLongPressPending || isLongPressActive;
  const isPressed = isHandlePressed || isContentPressed;
  const isDarkPressed = isLongPressActive;
  const textColor = isDarkPressed ? "var(--gray-1)" : undefined;

  // Menyinggahkan objek gaya
  const style = useMemo(
    () => ({
      transform: dragOffset === 0 ? undefined : `translateY(${dragOffset}px)`,
      transition: getEntryListTransition(isDragActive),
      opacity: shouldHideDraggedEntry({ isDragSource }) ? 0 : isPressed ? 0.5 : 1,
      borderBottom: isSelected ? "1px solid var(--gray-6)" : "1px solid var(--gray-a5)",
      background: isDarkPressed
        ? "var(--gray-12)"
        : isSelected
          ? "var(--accent-a3)"
          : "transparent",
      cursor: "pointer",
      height: ENTRY_LIST_ITEM_HEIGHT,
      width: "100%",
      minWidth: 0,
      overflow: "hidden",
      contain: "layout style" as const,
      position: isLanding ? ("relative" as const) : undefined,
      zIndex: isLanding ? 1 : undefined,
      boxShadow: isLanding ? "0 4px 12px var(--gray-a5)" : undefined,
      touchAction: isDragging ? "none" : "pan-y",
      userSelect: "none" as const,
      WebkitUserSelect: "none" as const,
      WebkitTouchCallout: "none" as const,
      WebkitTapHighlightColor: "transparent",
    }),
    [
      isDragActive,
      dragOffset,
      isDragging,
      isDragSource,
      isPressed,
      isDarkPressed,
      isSelected,
      isLanding,
    ],
  );

  useEffect(() => {
    if (!isHandlePressed && !isLongPressPending && !isLongPressActive) return;

    const handleRelease = () => {
      setIsHandlePressed(false);
      setIsLongPressPending(false);
      setIsLongPressActive(false);
    };
    window.addEventListener("pointerup", handleRelease);
    window.addEventListener("pointercancel", handleRelease);
    return () => {
      window.removeEventListener("pointerup", handleRelease);
      window.removeEventListener("pointercancel", handleRelease);
    };
  }, [isHandlePressed, isLongPressPending, isLongPressActive]);

  useEffect(
    () => () => {
      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
      }
    },
    [],
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
    setIsHandlePressed(false);
  }, [clearLongPress]);

  const triggerLongPressMenu = useCallback(() => {
    const position = longPressPositionRef.current;
    if (!position) return;

    longPressTriggeredRef.current = true;
    setIsLongPressPending(false);
    setIsLongPressActive(true);
    suppressContextMenuRef.current = true;

    const selection = window.getSelection();
    selection?.removeAllRanges();

    onContextMenu(entry.id, position);
  }, [onContextMenu, entry.id]);

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();

      if (suppressContextMenuRef.current) {
        suppressContextMenuRef.current = false;
        return;
      }

      longPressTriggeredRef.current = false;
      resetPressState();
      onContextMenu(entry.id, { x: e.clientX, y: e.clientY });
    },
    [onContextMenu, resetPressState, entry.id],
  );

  const handleDragHandlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.stopPropagation();
      resetPressState();
      setIsHandlePressed(true);
      listeners?.onPointerDown?.(e);
    },
    [listeners, resetPressState],
  );

  const handleDragHandleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
      e.preventDefault();
      e.stopPropagation();
      onKeyboardReorder(entry.id, e.key === "ArrowUp" ? -1 : 1);
    },
    [entry.id, onKeyboardReorder],
  );

  const handleContentPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (e.pointerType === "mouse" || e.button !== 0) return;

      if (suppressContextMenuRef.current) return;

      onLongPressStart();
      longPressTriggeredRef.current = false;
      setIsLongPressActive(false);
      setIsLongPressPending(true);
      longPressPositionRef.current = { x: e.clientX, y: e.clientY };

      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
      }

      longPressTimeoutRef.current = window.setTimeout(() => {
        longPressTimeoutRef.current = null;
        triggerLongPressMenu();
      }, 280);
    },
    [onLongPressStart, triggerLongPressMenu],
  );

  const handleHandleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      suppressContextMenuRef.current = false;
      resetPressState();
    },
    [resetPressState],
  );

  const handleContentPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const position = longPressPositionRef.current;
      if (!position || !isLongPressPending) return;

      if (Math.abs(e.clientX - position.x) > 8 || Math.abs(e.clientY - position.y) > 8) {
        resetPressState();
      }
    },
    [isLongPressPending, resetPressState],
  );

  const handleContentPointerUp = useCallback(() => {
    resetPressState();
    window.getSelection()?.removeAllRanges();
  }, [resetPressState]);

  const handleClick = useCallback(() => {
    if (isMultiSelect) {
      onCheckChange?.(entry.id);
      return;
    }

    if (longPressTriggeredRef.current) {
      longPressTriggeredRef.current = false;
      return;
    }

    onClick(entry.id);
  }, [isMultiSelect, onClick, onCheckChange, entry.id]);

  return (
    <Box
      ref={setCombinedRef}
      data-entry-id={entry.id}
      style={style}
      onClick={handleClick}
      onContextMenu={handleContextMenu}
      onPointerDown={handleContentPointerDown}
      onPointerMove={handleContentPointerMove}
      onPointerUp={handleContentPointerUp}
      onPointerCancel={handleContentPointerUp}
    >
      <Flex
        align="stretch"
        justify="between"
        style={{ minWidth: 0, width: "100%" }}
      >
        {isMultiSelect ? (
          <Flex
            align="center"
            justify="center"
            style={{
              width: 44,
              minWidth: 44,
              flexShrink: 0,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <Checkbox
              checked={isChecked}
              onCheckedChange={() => onCheckChange?.(entry.id)}
              size="1"
            />
          </Flex>
        ) : showDragHandle ? (
          <Flex
            {...attributes}
            align="center"
            justify="center"
            style={{
              width: 44,
              minWidth: 44,
              flexShrink: 0,
              cursor: isDragging ? "grabbing" : "grab",
              color: "var(--gray-a9)",
              touchAction: "none",
            }}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={isDragOverlay ? undefined : handleDragHandlePointerDown}
            onKeyDown={handleDragHandleKeyDown}
            onContextMenu={handleHandleContextMenu}
          >
            <GripVertical size={16} />
          </Flex>
        ) : (
          <Box style={{ width: 44, minWidth: 44, flexShrink: 0 }} />
        )}

        <Flex
          align="center"
          gap="2"
          justify="between"
          style={{
            flex: 1,
            minWidth: 0,
            padding: "12px 12px 12px 0",
          }}
        >
          <Flex
            direction="column"
            gap="1"
            style={{ flex: 1, minWidth: 0, overflow: "hidden" }}
          >
            <Flex
              align="center"
              style={{ minWidth: 0, width: "100%" }}
            >
              <Box style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
                <Text
                  size="2"
                  weight="medium"
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    display: "block",
                    width: "100%",
                    color: textColor,
                    userSelect: "none",
                    WebkitUserSelect: "none",
                  }}
                >
                  {entry.name}
                </Text>
              </Box>
            </Flex>
            <Flex gap="2">
              <Text
                size="1"
                color={isDarkPressed ? undefined : "gray"}
                style={{ color: isDarkPressed ? textColor : undefined }}
              >
                {entry.tokenCount} {t("worldInfo.tokenCount")}
              </Text>
              <Text
                size="1"
                color={isDarkPressed ? undefined : "gray"}
                style={{ color: isDarkPressed ? textColor : undefined }}
              >
                · {formatRelativeTime(entry.updatedAt)}
              </Text>
            </Flex>
          </Flex>

          <Flex
            align="center"
            gap="1"
            style={{ flexShrink: 0 }}
          >
            <Switch
              size="1"
              checked={entry.isEnabled}
              onClick={(e) => e.stopPropagation()}
              onCheckedChange={() => onToggle(entry.id)}
            />
          </Flex>
        </Flex>
      </Flex>
    </Box>
  );
}

// Membungkus komponen memakai memo, fungsi pembanding kustom untuk mengoptimalkan kinerja
export const EntryListItem = memo(
  EntryListItemComponent,
  (prev, next) =>
    prev.entry.id === next.entry.id &&
    prev.entry.name === next.entry.name &&
    prev.entry.tokenCount === next.entry.tokenCount &&
    prev.entry.isEnabled === next.entry.isEnabled &&
    prev.entry.updatedAt === next.entry.updatedAt &&
    prev.isSelected === next.isSelected &&
    prev.showDragHandle === next.showDragHandle &&
    prev.isMultiSelect === next.isMultiSelect &&
    prev.isChecked === next.isChecked &&
    prev.isDragSource === next.isDragSource &&
    prev.dragOffset === next.dragOffset &&
    prev.isDragOverlay === next.isDragOverlay,
);
