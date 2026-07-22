import { useDraggable, useDroppable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Flex, Text } from "@radix-ui/themes";
import {
  Folder,
  FolderOpen,
  NotebookText,
  Lock,
  EyeOff,
  MoreHorizontal,
  ChevronRight,
} from "lucide-react";
import { memo, useCallback, useRef, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const MOBILE_LONG_PRESS_MS = 280;
const MOBILE_LONG_PRESS_MOVE_TOLERANCE = 8;

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
    [handleSubmit, onCancel],
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

export interface NoteTreeItemData {
  type: "category" | "note";
  id: string;
  title: string;
  parentId: string | null;
  depth: number;
  ancestorCategoryIds: string[];
  isLocked?: boolean;
  isHidden?: boolean;
  isExpanded?: boolean;
  childCount?: number;
}

interface NoteTreeItemProps {
  data: NoteTreeItemData;
  isActive: boolean;
  isRenaming: boolean;
  activeAncestorCategoryIds: Set<string>;
  onSelect: (id: string, type: "category" | "note") => void;
  onExpand: (id: string) => void;
  onContextMenu: (
    id: string,
    type: "category" | "note",
    position: { x: number; y: number },
    title: string,
  ) => void;
  onRenameConfirm: (id: string, type: "category" | "note", newTitle: string) => void;
  onRenameCancel: () => void;
}

export const NoteTreeItem = memo(function NoteTreeItem({
  data,
  isActive,
  isRenaming,
  activeAncestorCategoryIds,
  onSelect,
  onExpand,
  onContextMenu,
  onRenameConfirm,
  onRenameCancel,
}: NoteTreeItemProps) {
  const { t } = useTranslation();
  const [isHovered, setIsHovered] = useState(false);
  const [isLongPressPending, setIsLongPressPending] = useState(false);
  const [isLongPressActive, setIsLongPressActive] = useState(false);
  const longPressTimeoutRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const longPressPositionRef = useRef<{ x: number; y: number } | null>(null);
  const suppressContextMenuRef = useRef(false);
  const didDragAfterLongPressRef = useRef(false);

  const draggableId = `${data.type}:${data.id}`;
  const isCategory = data.type === "category";

  const {
    attributes,
    listeners,
    setNodeRef: setDragNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: draggableId,
    data: {
      itemType: data.type,
      itemId: data.id,
      depth: data.depth,
      parentId: data.parentId,
    },
  });

  const { setNodeRef: setDropNodeRef, isOver } = useDroppable({
    id: `${draggableId}:drop`,
    data: {
      itemType: "category",
      itemId: data.id,
      depth: data.depth,
    },
    disabled: !isCategory,
  });

  const setNodeRef = useCallback(
    (node: HTMLElement | null) => {
      setDragNodeRef(node);
      if (isCategory) setDropNodeRef(node);
    },
    [setDragNodeRef, setDropNodeRef, isCategory],
  );

  const highlight = isCategory && isOver && !isDragging;

  const isPressed = isLongPressPending || isLongPressActive;
  const isDarkPressed = isLongPressActive;
  const isPendingPressed = isLongPressPending && !isLongPressActive;
  const textColor = isDarkPressed ? "var(--gray-1)" : undefined;

  const rowBackground = isDarkPressed
    ? "var(--gray-12)"
    : isPendingPressed
      ? "var(--gray-a6)"
      : highlight
        ? "var(--accent-a4)"
        : isActive
          ? "var(--accent-a3)"
          : isHovered
            ? "var(--gray-a3)"
            : "transparent";

  const style = {
    transform: CSS.Translate.toString(transform),
    transition: isDragging
      ? "none"
      : "background-color 0.08s ease, color 0.08s ease, opacity 0.08s ease",
    opacity: isDragging ? 0.4 : isPressed ? 0.5 : 1,
    position: "relative" as const,
    cursor: isDragging ? "grabbing" : "pointer",
    touchAction: "pan-y",
    userSelect: "none" as const,
    WebkitUserSelect: "none" as const,
    WebkitTouchCallout: "none" as const,
    WebkitTapHighlightColor: "transparent",
  };

  const BASE_INDENT = 8;
  const INDENT_STEP = 16;
  const CHEVRON_GUTTER = 18;
  const contentPaddingLeft = BASE_INDENT + data.depth * INDENT_STEP;

  const handleContextMenu = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();

      if (suppressContextMenuRef.current) {
        suppressContextMenuRef.current = false;
        return;
      }

      longPressTriggeredRef.current = false;
      setIsLongPressPending(false);
      setIsLongPressActive(false);
      onContextMenu(data.id, data.type, { x: event.clientX, y: event.clientY }, data.title);
    },
    [data.id, data.type, data.title, onContextMenu],
  );

  const handleOpenMenu = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation();
      const rect = event.currentTarget.getBoundingClientRect();
      onContextMenu(data.id, data.type, { x: rect.right - 4, y: rect.bottom + 4 }, data.title);
    },
    [data.id, data.type, data.title, onContextMenu],
  );

  const iconSize = 14;
  const Icon = data.type === "category" ? (data.isExpanded ? FolderOpen : Folder) : NotebookText;

  const handleRowClick = useCallback(() => {
    if (longPressTriggeredRef.current) {
      longPressTriggeredRef.current = false;
      return;
    }

    if (data.type === "category") {
      onExpand(data.id);
    }
    onSelect(data.id, data.type);
  }, [data.id, data.type, onExpand, onSelect]);

  useEffect(() => {
    if (!isLongPressPending && !isLongPressActive) return;

    const handlePointerUp = () => {
      if (isLongPressActive && !didDragAfterLongPressRef.current) {
        const position = longPressPositionRef.current;
        if (position && !isRenaming) {
          longPressTriggeredRef.current = true;
          suppressContextMenuRef.current = true;
          onContextMenu(data.id, data.type, position, data.title);
        }
      }

      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
        longPressTimeoutRef.current = null;
      }
      setIsLongPressPending(false);
      setIsLongPressActive(false);
      didDragAfterLongPressRef.current = false;
      window.getSelection()?.removeAllRanges();
    };

    const handlePointerCancel = () => {
      setIsLongPressPending(false);
      setIsLongPressActive(false);
      didDragAfterLongPressRef.current = false;
      window.getSelection()?.removeAllRanges();
    };

    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerCancel);
    return () => {
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerCancel);
    };
  }, [
    data.id,
    data.title,
    data.type,
    isLongPressActive,
    isLongPressPending,
    isRenaming,
    onContextMenu,
  ]);

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
    didDragAfterLongPressRef.current = false;
  }, [clearLongPress]);

  const activateLongPress = useCallback(() => {
    setIsLongPressPending(false);
    setIsLongPressActive(true);
    suppressContextMenuRef.current = true;
    window.getSelection()?.removeAllRanges();
  }, []);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      listeners?.onPointerDown?.(event);

      if (isRenaming) return;
      if (event.pointerType === "mouse" || event.button !== 0) return;

      window.getSelection()?.removeAllRanges();
      longPressTriggeredRef.current = false;
      didDragAfterLongPressRef.current = false;
      setIsLongPressActive(false);
      setIsLongPressPending(true);
      longPressPositionRef.current = { x: event.clientX, y: event.clientY };

      if (longPressTimeoutRef.current !== null) {
        window.clearTimeout(longPressTimeoutRef.current);
      }

      longPressTimeoutRef.current = window.setTimeout(() => {
        longPressTimeoutRef.current = null;
        activateLongPress();
      }, MOBILE_LONG_PRESS_MS);
    },
    [activateLongPress, isRenaming, listeners],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const position = longPressPositionRef.current;
      if (!position) return;

      const movedBeyondTolerance =
        Math.abs(event.clientX - position.x) > MOBILE_LONG_PRESS_MOVE_TOLERANCE ||
        Math.abs(event.clientY - position.y) > MOBILE_LONG_PRESS_MOVE_TOLERANCE;

      if (isLongPressActive && movedBeyondTolerance) {
        didDragAfterLongPressRef.current = true;
        return;
      }

      if (!isLongPressPending) return;

      if (movedBeyondTolerance) {
        resetPressState();
      }
    },
    [isLongPressActive, isLongPressPending, resetPressState],
  );

  const guideLines = Array.from({ length: data.depth }, (_, index) => {
    const left = BASE_INDENT + index * INDENT_STEP + CHEVRON_GUTTER / 2;
    const ancestorId = data.ancestorCategoryIds[index];
    const isActivePath = ancestorId !== undefined && activeAncestorCategoryIds.has(ancestorId);
    return (
      <span
        key={`guide-${index}`}
        aria-hidden="true"
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left,
          width: 1,
          background: isActivePath ? "var(--gray-a7)" : "var(--gray-a4)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
    );
  });

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onPointerEnter={(event) => {
        if (event.pointerType === "mouse") {
          setIsHovered(true);
        }
      }}
      onPointerLeave={(event) => {
        if (event.pointerType === "mouse") {
          setIsHovered(false);
        }
      }}
      onClick={handleRowClick}
      onContextMenu={handleContextMenu}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
    >
      {guideLines}

      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 0,
          right: 0,
          background: rowBackground,
          boxShadow: highlight ? "inset 0 0 0 1.5px var(--accent-a8)" : undefined,
          borderRadius: 6,
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      <Flex
        gap="2"
        align="center"
        style={{
          minWidth: 0,
          padding: "6px 12px",
          paddingLeft: contentPaddingLeft,
          position: "relative",
          zIndex: 2,
        }}
      >
        {data.type === "category" ? (
          <span
            style={{
              width: CHEVRON_GUTTER,
              height: 18,
              flexShrink: 0,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ChevronRight
              size={12}
              style={{
                color: textColor,
                transform: data.isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                transition: "transform 0.15s ease",
              }}
            />
          </span>
        ) : (
          <span
            style={{ width: CHEVRON_GUTTER, flexShrink: 0 }}
            aria-hidden="true"
          />
        )}

        <Icon
          size={iconSize}
          style={{ flexShrink: 0, opacity: 0.55, color: textColor }}
        />

        <Box style={{ flex: 1, minWidth: 0 }}>
          {isRenaming ? (
            <RenameInput
              key={data.id}
              initialValue={data.title}
              onConfirm={(newTitle) => onRenameConfirm(data.id, data.type, newTitle)}
              onCancel={onRenameCancel}
            />
          ) : (
            <Text
              size="2"
              weight="medium"
              style={{
                display: "block",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                color: textColor,
              }}
            >
              {data.title ||
                (data.type === "category"
                  ? t("writing.untitledCategory")
                  : t("writing.untitledNote"))}
            </Text>
          )}
        </Box>

        <Flex
          align="center"
          gap="1"
          style={{ flexShrink: 0 }}
        >
          {data.isLocked && (
            <Lock
              size={12}
              style={{ opacity: 0.4, color: textColor }}
            />
          )}
          {data.isHidden && (
            <EyeOff
              size={12}
              style={{ opacity: 0.4, color: textColor }}
            />
          )}

          {isHovered && (
            <button
              type="button"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={handleOpenMenu}
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
                cursor: "pointer",
              }}
            >
              <MoreHorizontal size={14} />
            </button>
          )}
        </Flex>
      </Flex>
    </div>
  );
});

function Box({ style, children }: { style?: React.CSSProperties; children: React.ReactNode }) {
  return <div style={style}>{children}</div>;
}
