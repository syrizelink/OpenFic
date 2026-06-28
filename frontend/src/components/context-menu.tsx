/**
 * Context Menu Component
 *
 * 通用右键菜单组件，支持两种模式：
 * 1. 手动模式：通过 position 和 items 手动控制
 * 2. 编辑器模式：通过 containerRef 自动监听右键，通过 editor 自动生成编辑器菜单项
 */

import { useState, useCallback, useEffect, useLayoutEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { Box, Flex, Text } from "@radix-ui/themes";
import { motion, AnimatePresence } from "motion/react";
import { useTranslation } from "react-i18next";
import { Scissors, Copy, Clipboard } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Editor } from "@tiptap/react";

const MOBILE_POINTER_LONG_PRESS_MS = 280;
const MOBILE_POINTER_MOVE_TOLERANCE = 8;

/** 菜单项接口 */
export interface ContextMenuItem {
  id: string;
  label: string;
  icon?: LucideIcon;
  shortcut?: string;
  disabled?: boolean;
  /** 危险操作（显示红色） */
  danger?: boolean;
  onClick: () => void;
}

/** 菜单位置 */
export interface ContextMenuPosition {
  x: number;
  y: number;
}

interface ContextMenuProps {
  /** 菜单位置，为 null 时隐藏（手动模式） */
  position?: ContextMenuPosition | null;
  /** 菜单项列表（手动模式） */
  items?: ContextMenuItem[];
  /** 关闭回调（手动模式） */
  onClose?: () => void;
  /** 编辑器实例（编辑器模式） */
  editor?: Editor | null;
  /** 容器元素引用，用于限制右键菜单触发范围（编辑器模式） */
  containerRef?: React.RefObject<HTMLElement | null>;
  /** 编辑器模式附加菜单项 */
  editorExtraItems?: (editor: Editor) => ContextMenuItem[];
}

/** 菜单项样式 */
const menuItemStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 8,
  padding: "6px 10px",
  cursor: "pointer",
  borderRadius: 4,
  transition: "background-color 0.1s ease",
};

export function ContextMenu({
  position: externalPosition,
  items: externalItems,
  onClose: externalOnClose,
  editor,
  containerRef,
  editorExtraItems,
}: ContextMenuProps) {
  const { t } = useTranslation();
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [internalPosition, setInternalPosition] =
    useState<ContextMenuPosition | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const themeWrapperRef = useRef<HTMLDivElement | null>(null);
  const [menuSize, setMenuSize] = useState({ width: 180, height: 0 });
  const mobilePointerRef = useRef<{
    pointerId: number;
    x: number;
    y: number;
    lastX: number;
    lastY: number;
    isLongPress: boolean;
  } | null>(null);
  const mobileLongPressTimerRef = useRef<number | null>(null);
  const suppressNextEditorContextMenuRef = useRef(false);
  const editorInputModeRestoreRef = useRef<string | null>(null);

  // 判断使用哪种模式
  const isEditorMode = !!editor && !!containerRef;

  // 使用内部位置（编辑器模式）或外部位置（手动模式）
  const position = isEditorMode ? internalPosition : externalPosition ?? null;
  const onClose = useCallback(() => {
    if (isEditorMode) {
      setInternalPosition(null);
      setHoveredItem(null);
    } else {
      externalOnClose?.();
    }
  }, [isEditorMode, externalOnClose]);

  const instanceId = useId();

  // 打开时通知其他 ContextMenu 关闭
  useEffect(() => {
    if (!position) return;
    document.dispatchEvent(
      new CustomEvent("context-menu:opened", { detail: { id: instanceId } })
    );
  }, [position, instanceId]);

  // 其他 ContextMenu 打开时关闭自身
  useEffect(() => {
    const handler = (e: Event) => {
      if ((e as CustomEvent<{ id: string }>).detail.id !== instanceId) {
        onClose();
      }
    };
    document.addEventListener("context-menu:opened", handler);
    return () => document.removeEventListener("context-menu:opened", handler);
  }, [instanceId, onClose]);

  // 编辑器模式：处理右键点击
  const handleContextMenu = useCallback(
    (e: MouseEvent) => {
      if (!isEditorMode || !containerRef?.current) return;
      if (suppressNextEditorContextMenuRef.current) {
        suppressNextEditorContextMenuRef.current = false;
        e.preventDefault();
        return;
      }

      // 确保点击在容器内
      if (!containerRef.current.contains(e.target as Node)) {
        return;
      }

      e.preventDefault();
      setInternalPosition({ x: e.clientX, y: e.clientY });
    },
    [isEditorMode, containerRef]
  );

  // 编辑器模式：监听容器右键事件
  useEffect(() => {
    if (!isEditorMode || !containerRef?.current) return;

    const container = containerRef.current;
    container.addEventListener("contextmenu", handleContextMenu);

    return () => {
      container.removeEventListener("contextmenu", handleContextMenu);
    };
  }, [isEditorMode, containerRef, handleContextMenu]);

  const clearMobileLongPressTimer = useCallback(() => {
    if (mobileLongPressTimerRef.current !== null) {
      window.clearTimeout(mobileLongPressTimerRef.current);
      mobileLongPressTimerRef.current = null;
    }
  }, []);

  const clearMobilePointer = useCallback(() => {
    clearMobileLongPressTimer();
    mobilePointerRef.current = null;
  }, [clearMobileLongPressTimer]);

  const suppressEditorKeyboard = useCallback(() => {
    const editorElement = editor?.view.dom;
    if (!editorElement) return;

    editorInputModeRestoreRef.current = editorElement.getAttribute("inputmode");
    editorElement.setAttribute("inputmode", "none");
  }, [editor]);

  const restoreEditorKeyboard = useCallback(() => {
    const editorElement = editor?.view.dom;
    if (!editorElement) return;

    const previousInputMode = editorInputModeRestoreRef.current;
    if (previousInputMode === null) {
      editorElement.removeAttribute("inputmode");
    } else {
      editorElement.setAttribute("inputmode", previousInputMode);
    }
    editorInputModeRestoreRef.current = null;
  }, [editor]);

  useEffect(
    () => () => {
      clearMobilePointer();
      restoreEditorKeyboard();
    },
    [clearMobilePointer, restoreEditorKeyboard]
  );

  useEffect(() => {
    if (!isEditorMode || !containerRef?.current) return;

    const container = containerRef.current;

    const handlePointerDown = (event: PointerEvent) => {
      if (event.pointerType === "mouse" || event.button !== 0) return;
      if (!container.contains(event.target as Node)) return;
      if (!(event.target as HTMLElement | null)?.closest(".ProseMirror")) return;

      clearMobilePointer();
      setInternalPosition(null);
      suppressEditorKeyboard();
      mobilePointerRef.current = {
        pointerId: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        lastX: event.clientX,
        lastY: event.clientY,
        isLongPress: false,
      };

      mobileLongPressTimerRef.current = window.setTimeout(() => {
        if (!mobilePointerRef.current) return;
        mobilePointerRef.current.isLongPress = true;
        editor?.view.dom.blur();
      }, MOBILE_POINTER_LONG_PRESS_MS);
    };

    const handlePointerMove = (event: PointerEvent) => {
      const pointer = mobilePointerRef.current;
      if (!pointer || pointer.pointerId !== event.pointerId) return;

      pointer.lastX = event.clientX;
      pointer.lastY = event.clientY;

      const hasMoved =
        Math.abs(event.clientX - pointer.x) > MOBILE_POINTER_MOVE_TOLERANCE ||
        Math.abs(event.clientY - pointer.y) > MOBILE_POINTER_MOVE_TOLERANCE;
      if (hasMoved && !pointer.isLongPress) {
        clearMobilePointer();
      }
    };

    const handlePointerUp = (event: PointerEvent) => {
      const pointer = mobilePointerRef.current;
      if (!pointer || pointer.pointerId !== event.pointerId) return;

      clearMobileLongPressTimer();
      if (pointer.isLongPress) {
        event.preventDefault();
        event.stopPropagation();
        suppressNextEditorContextMenuRef.current = true;
        const releaseX = event.clientX || pointer.lastX;
        const releaseY = event.clientY || pointer.lastY;
        setInternalPosition({ x: releaseX, y: releaseY });
      }
      window.setTimeout(restoreEditorKeyboard, 0);
      mobilePointerRef.current = null;
    };

    const handlePointerCancel = (event: PointerEvent) => {
      const pointer = mobilePointerRef.current;
      if (!pointer || pointer.pointerId !== event.pointerId) return;
      clearMobilePointer();
      restoreEditorKeyboard();
    };

    const handleContextMenuCapture = (event: Event) => {
      const pointer = mobilePointerRef.current;
      if (!pointer && !suppressNextEditorContextMenuRef.current) return;
      if (!(event.target as HTMLElement | null)?.closest(".ProseMirror")) return;

      event.preventDefault();
      event.stopPropagation();
      suppressNextEditorContextMenuRef.current = false;
    };

    container.addEventListener("pointerdown", handlePointerDown, { capture: true });
    container.addEventListener("pointermove", handlePointerMove, { capture: true });
    container.addEventListener("pointerup", handlePointerUp, { capture: true });
    container.addEventListener("pointercancel", handlePointerCancel, { capture: true });
    container.addEventListener("contextmenu", handleContextMenuCapture, { capture: true });

    return () => {
      container.removeEventListener("pointerdown", handlePointerDown, { capture: true });
      container.removeEventListener("pointermove", handlePointerMove, { capture: true });
      container.removeEventListener("pointerup", handlePointerUp, { capture: true });
      container.removeEventListener("pointercancel", handlePointerCancel, { capture: true });
      container.removeEventListener("contextmenu", handleContextMenuCapture, { capture: true });
    };
  }, [clearMobileLongPressTimer, clearMobilePointer, containerRef, editor, isEditorMode, restoreEditorKeyboard, suppressEditorKeyboard]);

  // 编辑器模式：生成编辑器菜单项
  const editorItems: ContextMenuItem[] = (() => {
    if (!editor) return [];

    // 检查是否有选中文本
    const hasSelection =
      editor.state.selection.from !== editor.state.selection.to;

    // 处理剪切
    const handleCut = () => {
      const { from, to } = editor.state.selection;
      const selectedText = editor.state.doc.textBetween(from, to, " ");

      if (selectedText) {
        navigator.clipboard.writeText(selectedText);
        editor.chain().focus().deleteSelection().run();
      }
      onClose();
    };

    // 处理复制
    const handleCopy = () => {
      const { from, to } = editor.state.selection;
      const selectedText = editor.state.doc.textBetween(from, to, " ");

      if (selectedText) {
        navigator.clipboard.writeText(selectedText);
      }
      onClose();
    };

    // 处理粘贴
    const handlePaste = async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          editor.chain().focus().insertContent(text).run();
        }
      } catch {
        // 剪贴板访问被拒绝
      }
      onClose();
    };

    const baseItems = [
      {
        id: "cut",
        label: t("editor.cut"),
        icon: Scissors,
        shortcut: "Ctrl+X",
        onClick: handleCut,
        disabled: !hasSelection,
      },
      {
        id: "copy",
        label: t("editor.copy"),
        icon: Copy,
        shortcut: "Ctrl+C",
        onClick: handleCopy,
        disabled: !hasSelection,
      },
      {
        id: "paste",
        label: t("editor.paste"),
        icon: Clipboard,
        shortcut: "Ctrl+V",
        onClick: handlePaste,
        disabled: false,
      },
    ];
    const extraItems = editorExtraItems ? editorExtraItems(editor) : [];
    return [...extraItems, ...baseItems];
  })();

  // 使用编辑器菜单项或外部菜单项
  const items = isEditorMode ? editorItems : externalItems ?? [];

  // 点击外部关闭
  useEffect(() => {
    if (!position) return;

    const handleClick = () => onClose();
    const handleScroll = () => onClose();

    document.addEventListener("click", handleClick);
    document.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("click", handleClick);
      document.removeEventListener("scroll", handleScroll, true);
    };
  }, [position, onClose]);

  // ESC 关闭菜单
  useEffect(() => {
    if (!position) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [position, onClose]);

  // 点击菜单项
  const handleItemClick = useCallback(
    (item: ContextMenuItem, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!item.disabled) {
        item.onClick();
        onClose();
      }
    },
    [onClose]
  );

  // 计算菜单位置，避免超出视口
  useLayoutEffect(() => {
    if (!position || !menuRef.current) return;

    const rect = menuRef.current.getBoundingClientRect();
    setMenuSize({ width: rect.width, height: rect.height });
  }, [items.length, position]);

  useLayoutEffect(() => {
    const themeRoot = document.querySelector(".radix-themes");
    const themeWrapper = themeWrapperRef.current;
    if (!(themeRoot instanceof HTMLElement) || !themeWrapper) return;

    themeWrapper.className = themeRoot.className;

    for (const attr of Array.from(themeWrapper.attributes)) {
      if (attr.name.startsWith("data-")) themeWrapper.removeAttribute(attr.name);
    }

    for (const attr of Array.from(themeRoot.attributes)) {
      if (attr.name.startsWith("data-")) {
        themeWrapper.setAttribute(attr.name, attr.value);
      }
    }

    themeWrapper.style.cssText = themeRoot.style.cssText;
    themeWrapper.style.position = "fixed";
    themeWrapper.style.inset = "0";
    themeWrapper.style.width = "0";
    themeWrapper.style.height = "0";
    themeWrapper.style.overflow = "visible";
    themeWrapper.style.pointerEvents = "none";
  }, [position]);

  const viewportPadding = 8;
  const menuWidth = menuSize.width;
  const menuHeight = menuSize.height;
  const adjustedPosition = position
    ? {
        x: Math.min(
          Math.max(position.x, viewportPadding),
          Math.max(viewportPadding, window.innerWidth - menuWidth - viewportPadding)
        ),
        y: Math.min(
          Math.max(position.y, viewportPadding),
          Math.max(viewportPadding, window.innerHeight - menuHeight - viewportPadding)
        ),
      }
    : null;

  const content = (
    <AnimatePresence>
      {position && adjustedPosition && (
        <motion.div
          ref={menuRef}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.1 }}
          style={{
            position: "fixed",
            top: adjustedPosition.y,
            left: adjustedPosition.x,
            zIndex: 100000,
            pointerEvents: "auto",
            userSelect: "none",
            WebkitUserSelect: "none",
            WebkitTouchCallout: "none",
          }}
          onPointerDown={(event) => event.preventDefault()}
        >
          <Box
            style={{
              minWidth: 160,
              padding: 2,
              borderRadius: 8,
              background: "var(--color-background)",
              border: "1px solid var(--gray-a5)",
              boxShadow:
                "0 4px 16px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.08)",
            }}
          >
            <Flex direction="column">
              {items.map((item) => (
                <Box
                  key={item.id}
                  style={{
                    ...menuItemStyle,
                    opacity: item.disabled ? 0.4 : 1,
                    cursor: item.disabled ? "not-allowed" : "pointer",
                    backgroundColor:
                      hoveredItem === item.id && !item.disabled
                        ? "var(--gray-a3)"
                        : "transparent",
                  }}
                  onMouseEnter={() => !item.disabled && setHoveredItem(item.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                  onClick={(e) => handleItemClick(item, e)}
                >
                  <Flex align="center" gap="2">
                    {item.icon && (
                      <item.icon
                        size={14}
                        style={{
                          color: item.danger
                            ? "var(--red-11)"
                            : "var(--gray-a11)",
                        }}
                      />
                    )}
                    <Text
                      size="2"
                      style={{
                        color: item.danger ? "var(--red-11)" : undefined,
                      }}
                    >
                      {item.label}
                    </Text>
                  </Flex>
                  {item.shortcut && (
                    <Text size="1" style={{ color: "var(--gray-a9)" }}>
                      {item.shortcut}
                    </Text>
                  )}
                </Box>
              ))}
            </Flex>
          </Box>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (typeof document === "undefined") {
    return null;
  }

  if (!position) {
    return null;
  }

  const themeRoot = document.querySelector(".radix-themes");

  const portalContent = themeRoot instanceof HTMLElement ? (
    <div ref={themeWrapperRef}>
      {content}
    </div>
  ) : content;

  return createPortal(portalContent, document.body);
}
