/**
 * Editor Tabs Component
 *
 * 编辑器标签页栏，显示打开的标签页列表。
 * 支持拖拽排序。
 * 性能优化：使用 memo 和选择器避免不必要的重渲染。
 */

import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToFirstScrollableAncestor, restrictToHorizontalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { Flex, Text } from "@radix-ui/themes";
import {
  AtSign,
  FileText,
  Lock,
  NotebookText,
  PanelRightClose,
  PanelRightOpen,
  Unlock,
  X,
  XCircle,
} from "lucide-react";
import { AnimatePresence, motion, useIsPresent, useReducedMotion } from "motion/react";
import { memo, useCallback, useEffect, useRef, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { ContextMenu, type ContextMenuItem } from "@/components";
import { TabScrollbar } from "@/components/tab-scrollbar";
import { useAppShell } from "@/features/app-shell";
import { buildChapterMentionTag, buildNoteMentionTag } from "@/features/assistant/lib/mention-text";

import type { EditorTab } from "../lib/tab.types";
import { useTabs, useActiveTabId, useTabsStore } from "../store/use-tabs-store";

import "./editor-tabs.css";

interface SortableTabItemProps {
  tab: EditorTab;
  isActive: boolean;
  hasActiveBefore: boolean;
  hasActiveAfter: boolean;
  displayTitle: string;
  onActivate: () => void;
  onReveal: () => void;
  onClose: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

function TabShape({
  noLeftCurve = false,
  noRightCurve = false,
  isActive = false,
}: {
  noLeftCurve?: boolean;
  noRightCurve?: boolean;
  isActive?: boolean;
}) {
  const start = noLeftCurve ? 7.5 : 0;
  const end = noRightCurve ? 166.5 : 174;
  const outline = `M ${start} 29.5 ${noLeftCurve ? "" : "Q 7.5 29.5 7.5 22"} L 7.5 6.5 Q 7.5 0.5 13.5 0.5 H 160.5 Q 166.5 0.5 166.5 6.5 V 22 ${noRightCurve ? "L 166.5 29.5" : "Q 166.5 29.5 174 29.5"}`;
  return (
    <svg
      className={isActive ? "editor-tab-shape" : "editor-tab-shape editor-tab-shape-hover"}
      viewBox="0 0 174 30"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        className="editor-tab-shape-fill"
        d={`${outline} L ${end} 30 H ${start} Z`}
      />
      {isActive && (
        <path
          className="editor-tab-shape-border"
          d={outline}
        />
      )}
    </svg>
  );
}

/** 可排序的标签页项 */
const SortableTabItem = memo(function SortableTabItem({
  tab,
  isActive,
  hasActiveBefore,
  hasActiveAfter,
  displayTitle,
  onActivate,
  onReveal,
  onClose,
  onContextMenu,
}: SortableTabItemProps) {
  const { t } = useTranslation();
  const isPresent = useIsPresent();
  const shouldReduceMotion = useReducedMotion();
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tab.id, disabled: !isPresent });
  const Icon = tab.type === "chapter" ? FileText : NotebookText;

  return (
    <motion.div
      ref={setNodeRef}
      className="editor-tab"
      data-active={isActive}
      data-dragging={isDragging}
      data-exiting={!isPresent}
      inert={!isPresent}
      initial={shouldReduceMotion ? false : { width: 0 }}
      animate={{ width: 160 }}
      exit={{ width: 0 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.18, ease: "easeOut" }}
      onAnimationComplete={() => {
        if (isActive && isPresent) onReveal();
      }}
      style={{
        transform: transform ? `translate3d(${transform.x}px, 0, 0)` : undefined,
        transition,
      }}
      onContextMenu={onContextMenu}
      onMouseDown={(event) => {
        if (event.button === 1) event.preventDefault();
      }}
      onAuxClick={(event) => {
        if (event.button === 1 && !tab.isLocked) onClose();
      }}
    >
      <TabShape
        isActive={isActive}
        noLeftCurve={!isActive && hasActiveBefore}
        noRightCurve={!isActive && hasActiveAfter}
      />
      <button
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        type="button"
        role="tab"
        aria-selected={isActive}
        className="editor-tab-select"
        title={displayTitle}
        onClick={onActivate}
      >
        <Icon
          size={14}
          aria-hidden="true"
        />
        <span className="editor-tab-title">{displayTitle}</span>
      </button>
      {!tab.isLocked && (
        <button
          type="button"
          className="editor-tab-close"
          aria-label={t("rightSidebar.closeTab", { title: displayTitle })}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={onClose}
        >
          <X size={12} />
        </button>
      )}
    </motion.div>
  );
});

export function EmptyEditorTabs() {
  const { t } = useTranslation();

  return (
    <Flex
      align="center"
      justify="center"
      direction="column"
      gap="2"
      className="editor-tabs-empty"
    >
      <Text
        size="2"
        color="gray"
      >
        {t("rightSidebar.empty")}
      </Text>
      <Text
        size="1"
        color="gray"
      >
        {t("tabs.emptyHint")}
      </Text>
    </Flex>
  );
}

interface EditorTabsProps {
  onAddToConversation?: (markup: string) => void;
}

export function EditorTabs({ onAddToConversation }: EditorTabsProps) {
  const tabs = useTabs();
  const activeTabId = useActiveTabId();
  const actions = useTabsStore();
  return (
    <EditorTabBar
      {...actions}
      tabs={tabs}
      activeTabId={activeTabId}
      onAddToConversation={onAddToConversation}
      showMentionAction
    />
  );
}

interface EditorTabBarProps extends EditorTabsProps {
  showMentionAction?: boolean;
  tabs: EditorTab[];
  activeTabId: string | null;
  setActiveTab: (id: string) => void;
  closeTab: (id: string) => void;
  reorderTabs: (activeId: string, overId: string) => void;
  closeOtherTabs: (id: string) => void;
  closeAllTabs: () => void;
  toggleLock: (id: string) => void;
}

export function EditorTabBar({
  tabs,
  activeTabId,
  setActiveTab,
  closeTab,
  reorderTabs,
  closeOtherTabs,
  closeAllTabs,
  toggleLock,
  onAddToConversation,
  showMentionAction = false,
}: EditorTabBarProps) {
  const { t } = useTranslation();
  const { isAssistantSidebarOpen, openAssistantSidebar, closeAssistantSidebar } = useAppShell();
  const listRef = useRef<HTMLDivElement>(null);
  const previousTabIdsRef = useRef(new Set(tabs.map((tab) => tab.id)));
  const previousActiveTabIdRef = useRef<string | null | undefined>(undefined);
  const [draggedTab, setDraggedTab] = useState<EditorTab | null>(null);

  // 拖拽传感器
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 6,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  // 右键菜单状态
  const [contextMenuPos, setContextMenuPos] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [contextMenuTabId, setContextMenuTabId] = useState<string | null>(null);

  const revealActiveTab = useCallback(() => {
    listRef.current
      ?.querySelector('[aria-selected="true"]')
      ?.closest(".editor-tab")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, []);

  useEffect(() => {
    if (
      activeTabId !== previousActiveTabIdRef.current &&
      activeTabId &&
      previousTabIdsRef.current.has(activeTabId)
    ) {
      revealActiveTab();
    }
    previousTabIdsRef.current = new Set(tabs.map((tab) => tab.id));
    previousActiveTabIdRef.current = activeTabId;
  }, [activeTabId, revealActiveTab, tabs]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey || list.scrollWidth <= list.clientWidth) return;
      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? list.clientWidth : 1;
      event.preventDefault();
      list.scrollLeft += delta * scale;
    };
    list.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      list.removeEventListener("wheel", handleWheel);
    };
  }, []);

  // 激活标签页
  const handleActivate = useCallback(
    (tabId: string) => {
      setActiveTab(tabId);
    },
    [setActiveTab],
  );

  // 关闭标签页
  const handleClose = useCallback(
    (tabId: string) => {
      closeTab(tabId);
    },
    [closeTab],
  );

  // 打开右键菜单
  const handleContextMenu = useCallback((tabId: string, e: React.MouseEvent) => {
    e.preventDefault();
    setContextMenuTabId(tabId);
    setContextMenuPos({ x: e.clientX, y: e.clientY });
  }, []);

  // 关闭右键菜单
  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuTabId(null);
  }, []);

  // 拖拽结束
  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (over && active.id !== over.id) {
        reorderTabs(active.id as string, over.id as string);
      }
      setDraggedTab(null);
    },
    [reorderTabs],
  );

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuTabId) return [];
    const targetTab = tabs.find((tab) => tab.id === contextMenuTabId);
    if (!targetTab) return [];

    const items: ContextMenuItem[] = [];
    if (targetTab.refId && showMentionAction) {
      items.push({
        id: "addToConversation",
        label: t("tabs.addToConversation"),
        icon: AtSign,
        disabled: !onAddToConversation,
        onClick: () => {
          if (targetTab.type === "note") {
            onAddToConversation?.(
              buildNoteMentionTag({
                noteId: targetTab.refId!,
                label: targetTab.title.trim() || t("writing.untitledNote"),
              }),
            );
          } else {
            onAddToConversation?.(
              buildChapterMentionTag({
                chapterId: targetTab.refId!,
                label: targetTab.title.trim() || t("writing.untitledChapter"),
              }),
            );
          }
        },
      });
    }

    items.push(
      {
        id: "close",
        label: t("tabs.close"),
        icon: X,
        disabled: targetTab.isLocked,
        onClick: () => closeTab(contextMenuTabId),
      },
      {
        id: "closeOthers",
        label: t("tabs.closeOthers"),
        icon: XCircle,
        onClick: () => closeOtherTabs(contextMenuTabId),
      },
      {
        id: "closeAll",
        label: t("tabs.closeAll"),
        icon: XCircle,
        onClick: () => closeAllTabs(),
      },
      {
        id: "lock",
        label: targetTab.isLocked ? t("tabs.unlock") : t("tabs.lock"),
        icon: targetTab.isLocked ? Unlock : Lock,
        onClick: () => toggleLock(contextMenuTabId),
      },
    );

    return items;
  }, [
    closeAllTabs,
    closeOtherTabs,
    closeTab,
    contextMenuTabId,
    onAddToConversation,
    showMentionAction,
    t,
    tabs,
    toggleLock,
  ]);

  return (
    <>
      <div
        className="editor-tabs-toolbar"
        data-dragging={draggedTab !== null}
      >
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          modifiers={[restrictToHorizontalAxis, restrictToFirstScrollableAncestor]}
          onDragStart={({ active }) =>
            setDraggedTab(tabs.find((tab) => tab.id === active.id) ?? null)
          }
          onDragCancel={() => setDraggedTab(null)}
          onDragEnd={handleDragEnd}
        >
          <div
            ref={listRef}
            className="editor-tabs-list"
            id="editor-tabs-list"
            role="tablist"
          >
            <SortableContext
              items={tabs.map((t) => t.id)}
              strategy={horizontalListSortingStrategy}
            >
              <AnimatePresence initial={false}>
                {tabs.map((tab, index) => (
                  <SortableTabItem
                    key={tab.id}
                    tab={tab}
                    isActive={tab.id === activeTabId}
                    hasActiveBefore={tabs[index - 1]?.id === activeTabId}
                    hasActiveAfter={tabs[index + 1]?.id === activeTabId}
                    displayTitle={tab.title}
                    onActivate={() => handleActivate(tab.id)}
                    onReveal={revealActiveTab}
                    onClose={() => handleClose(tab.id)}
                    onContextMenu={(e) => handleContextMenu(tab.id, e)}
                  />
                ))}
              </AnimatePresence>
            </SortableContext>
          </div>
          <DragOverlay
            dropAnimation={{ duration: 180, easing: "ease-out" }}
            zIndex={70}
          >
            {draggedTab && (
              <div
                className="editor-tab editor-tab-overlay"
                data-active={draggedTab.id === activeTabId}
                aria-hidden="true"
              >
                {draggedTab.id === activeTabId && <TabShape isActive />}
                <span className="editor-tab-select">
                  {draggedTab.type === "chapter" ? (
                    <FileText size={14} />
                  ) : (
                    <NotebookText size={14} />
                  )}
                  <span className="editor-tab-title">{draggedTab.title}</span>
                </span>
                {!draggedTab.isLocked && (
                  <span className="editor-tab-close">
                    <X size={12} />
                  </span>
                )}
              </div>
            )}
          </DragOverlay>
        </DndContext>
        <TabScrollbar
          listRef={listRef}
          listId="editor-tabs-list"
          label={t("tabs.scrollTabs")}
          items={tabs}
          isDragging={draggedTab !== null}
        />
        <button
          type="button"
          className="editor-tabs-add editor-tabs-sidebar-open"
          aria-label={t(isAssistantSidebarOpen ? "rightSidebar.collapse" : "rightSidebar.expand")}
          title={t(isAssistantSidebarOpen ? "rightSidebar.collapse" : "rightSidebar.expand")}
          onClick={isAssistantSidebarOpen ? closeAssistantSidebar : openAssistantSidebar}
        >
          {isAssistantSidebarOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
        </button>
      </div>

      {/* 标签页右键菜单 */}
      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />
    </>
  );
}
