/**
 * Context Menu Component
 *
 * Komponen menu klik kanan serbaguna, mendukung dua mode:
 * 1. Mode manual: dikendalikan manual lewat position dan items
 * 2. Mode editor: memantau klik kanan otomatis lewat containerRef, item menu editor dibuat otomatis lewat editor
 */

import { Box, Flex, Text } from "@radix-ui/themes";
import type { Editor } from "@tiptap/react";
import { Scissors, Copy, Clipboard } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useState, useCallback, useEffect, useLayoutEffect, useId, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { readClipboardText, writeClipboardText } from "@/lib/clipboard";

import { toast } from "./toast";

const MOBILE_POINTER_LONG_PRESS_MS = 280;
const MOBILE_POINTER_MOVE_TOLERANCE = 8;

/** Antarmuka item menu */
export interface ContextMenuItem {
  id: string;
  label: string;
  icon?: LucideIcon;
  shortcut?: string;
  disabled?: boolean;
  /** Tindakan berbahaya (ditampilkan merah) */
  danger?: boolean;
  onClick: () => void;
}

/** Posisi menu */
export interface ContextMenuPosition {
  x: number;
  y: number;
}

interface ContextMenuProps {
  /** Posisi menu, disembunyikan saat null (mode manual) */
  position?: ContextMenuPosition | null;
  /** Daftar item menu (mode manual) */
  items?: ContextMenuItem[];
  /** Callback penutupan (mode manual) */
  onClose?: () => void;
  /** Instans editor (mode editor) */
  editor?: Editor | null;
  /** Referensi elemen wadah, membatasi jangkauan pemicu menu klik kanan (mode editor) */
  containerRef?: React.RefObject<HTMLElement | null>;
  /** Item menu tambahan untuk mode editor */
  editorExtraItems?: (editor: Editor) => ContextMenuItem[];
}

/** Gaya item menu */
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
  const [internalPosition, setInternalPosition] = useState<ContextMenuPosition | null>(null);
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
  const editorInputModeRestoreRef = useRef<string | null | undefined>(undefined);

  // Menentukan mode yang dipakai
  const isEditorMode = !!editor && !!containerRef;

  // Pada perangkat sentuh (coarse pointer) editor memakai menu sistem, menu editor kustom tidak diaktifkan
  const editorMenuDisabled = useMemo(
    () => isEditorMode && window.matchMedia("(pointer: coarse)").matches,
    [isEditorMode],
  );

  // Memakai posisi internal (mode editor) atau posisi eksternal (mode manual)
  const position = isEditorMode ? internalPosition : (externalPosition ?? null);
  const onClose = useCallback(() => {
    if (isEditorMode) {
      setInternalPosition(null);
      setHoveredItem(null);
    } else {
      externalOnClose?.();
    }
  }, [isEditorMode, externalOnClose]);

  const instanceId = useId();

  // Memberi tahu ContextMenu lain untuk menutup saat dibuka
  useEffect(() => {
    if (!position) return;
    document.dispatchEvent(new CustomEvent("context-menu:opened", { detail: { id: instanceId } }));
  }, [position, instanceId]);

  // Menutup diri sendiri saat ContextMenu lain dibuka
  useEffect(() => {
    const handler = (e: Event) => {
      if ((e as CustomEvent<{ id: string }>).detail.id !== instanceId) {
        onClose();
      }
    };
    document.addEventListener("context-menu:opened", handler);
    return () => document.removeEventListener("context-menu:opened", handler);
  }, [instanceId, onClose]);

  // Mode editor: menangani klik kanan
  const handleContextMenu = useCallback(
    (e: MouseEvent) => {
      if (!isEditorMode || editorMenuDisabled || !containerRef?.current) return;
      if (suppressNextEditorContextMenuRef.current) {
        suppressNextEditorContextMenuRef.current = false;
        e.preventDefault();
        return;
      }

      // Memastikan klik terjadi di dalam wadah
      if (!containerRef.current.contains(e.target as Node)) {
        return;
      }

      e.preventDefault();
      setInternalPosition({ x: e.clientX, y: e.clientY });
    },
    [isEditorMode, editorMenuDisabled, containerRef],
  );

  // Mode editor: memantau peristiwa klik kanan pada wadah
  useEffect(() => {
    if (!isEditorMode || editorMenuDisabled || !containerRef?.current) return;

    const container = containerRef.current;
    container.addEventListener("contextmenu", handleContextMenu);

    return () => {
      container.removeEventListener("contextmenu", handleContextMenu);
    };
  }, [isEditorMode, editorMenuDisabled, containerRef, handleContextMenu]);

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

    if (editorInputModeRestoreRef.current !== undefined) return;
    editorInputModeRestoreRef.current = editorElement.getAttribute("inputmode");
    editorElement.setAttribute("inputmode", "none");
  }, [editor]);

  const restoreEditorKeyboard = useCallback(() => {
    const editorElement = editor?.view.dom;
    if (!editorElement) return;

    const previousInputMode = editorInputModeRestoreRef.current;
    if (previousInputMode === undefined) return;
    if (previousInputMode === null) {
      editorElement.removeAttribute("inputmode");
    } else {
      editorElement.setAttribute("inputmode", previousInputMode);
    }
    editorInputModeRestoreRef.current = undefined;
  }, [editor]);

  useEffect(
    () => () => {
      clearMobilePointer();
      restoreEditorKeyboard();
    },
    [clearMobilePointer, restoreEditorKeyboard],
  );

  useEffect(() => {
    if (!isEditorMode || editorMenuDisabled || !containerRef?.current) return;

    const container = containerRef.current;

    const handlePointerDown = (event: PointerEvent) => {
      if (event.pointerType === "mouse" || event.button !== 0) return;
      if (!container.contains(event.target as Node)) return;
      if (!(event.target as HTMLElement | null)?.closest(".ProseMirror")) return;

      clearMobilePointer();
      setInternalPosition(null);
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
        suppressEditorKeyboard();
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
  }, [
    clearMobileLongPressTimer,
    clearMobilePointer,
    containerRef,
    editor,
    editorMenuDisabled,
    isEditorMode,
    restoreEditorKeyboard,
    suppressEditorKeyboard,
  ]);

  // Mode editor: membuat item menu editor
  const editorItems: ContextMenuItem[] = (() => {
    if (!editor) return [];

    // Memeriksa adanya teks yang dipilih
    const hasSelection = editor.state.selection.from !== editor.state.selection.to;

    // Menangani pemotongan
    const handleCut = async () => {
      const { from, to } = editor.state.selection;
      const selectedText = editor.state.doc.textBetween(from, to, " ");

      if (selectedText) {
        const copied = await writeClipboardText(selectedText);
        if (!copied) {
          toast.error(t("editor.copyFailed"));
          return;
        }
        editor.chain().deleteSelection().run();
      }
    };

    // Menangani penyalinan
    const handleCopy = async () => {
      const { from, to } = editor.state.selection;
      const selectedText = editor.state.doc.textBetween(from, to, " ");

      if (selectedText) {
        const copied = await writeClipboardText(selectedText);
        if (!copied) {
          toast.error(t("editor.copyFailed"));
        }
      }
    };

    // Menangani penempelan
    const handlePaste = async () => {
      const result = await readClipboardText();
      if (!result.ok) {
        toast.error(
          result.reason === "unavailable" ? t("editor.pasteUnavailable") : t("editor.pasteFailed"),
        );
        return;
      }
      if (!result.text) return;
      editor.chain().insertContent(result.text).run();
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

  // Memakai item menu editor atau item menu eksternal
  const items = isEditorMode ? editorItems : (externalItems ?? []);

  // Menutup saat diklik di luar
  useEffect(() => {
    if (!position) return;

    const handleClick = () => onClose();
    const handleScroll = () => onClose();
    let clickListenerAttached = false;

    const timerId = window.setTimeout(() => {
      document.addEventListener("click", handleClick);
      clickListenerAttached = true;
    }, 0);

    document.addEventListener("scroll", handleScroll, true);

    return () => {
      window.clearTimeout(timerId);
      if (clickListenerAttached) {
        document.removeEventListener("click", handleClick);
      }
      document.removeEventListener("scroll", handleScroll, true);
    };
  }, [position, onClose]);

  // ESC menutup menu
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

  // Mengeklik item menu
  const handleItemClick = useCallback(
    (item: ContextMenuItem, event: { stopPropagation: () => void }) => {
      event.stopPropagation();
      if (item.disabled) return;
      try {
        item.onClick();
      } finally {
        onClose();
      }
    },
    [onClose],
  );

  // Menghitung posisi menu agar tidak keluar dari viewport
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
          Math.max(viewportPadding, window.innerWidth - menuWidth - viewportPadding),
        ),
        y: Math.min(
          Math.max(position.y, viewportPadding),
          Math.max(viewportPadding, window.innerHeight - menuHeight - viewportPadding),
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
              boxShadow: "0 4px 16px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.08)",
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
                      hoveredItem === item.id && !item.disabled ? "var(--gray-a3)" : "transparent",
                  }}
                  onMouseEnter={() => !item.disabled && setHoveredItem(item.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                  onPointerUp={(e) => handleItemClick(item, e)}
                >
                  <Flex
                    align="center"
                    gap="2"
                  >
                    {item.icon && (
                      <item.icon
                        size={14}
                        style={{
                          color: item.danger ? "var(--red-11)" : "var(--gray-a11)",
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
                    <Text
                      size="1"
                      style={{ color: "var(--gray-a9)" }}
                    >
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

  const portalContent =
    themeRoot instanceof HTMLElement ? <div ref={themeWrapperRef}>{content}</div> : content;

  return createPortal(portalContent, document.body);
}
