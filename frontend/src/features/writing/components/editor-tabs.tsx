/**
 * Editor Tabs Component
 *
 * 编辑器标签页栏，显示打开的标签页列表。
 * 支持拖拽排序。
 * 性能优化：使用 memo 和选择器避免不必要的重渲染。
 */

import { memo, useCallback, useState, useMemo } from "react";
import { Box, Flex, Text, IconButton, Button } from "@radix-ui/themes";
import { AtSign, FilePlus, FileText, Lock, Plus, StickyNote, Unlock, X, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  restrictToHorizontalAxis,
  restrictToParentElement,
} from "@dnd-kit/modifiers";

import { useTabs, useActiveTabId, useTabsStore } from "../store/use-tabs-store";
import { ContextMenu, type ContextMenuItem } from "@/components";
import { buildChapterMentionTag, buildNoteMentionTag } from "@/features/assistant/lib/mention-text";
import { isEmptyTab } from "../lib/tab.types";
import type { EditorTab } from "../lib/tab.types";

/** 标签页尺寸配置 */
const TAB_MIN_WIDTH = 80;
const TAB_MAX_WIDTH = 160;

interface SortableTabItemProps {
  tab: EditorTab;
  isActive: boolean;
  displayTitle: string;
  onActivate: () => void;
  onClose: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

/** 可排序的标签页项 */
const SortableTabItem = memo(function SortableTabItem({
  tab,
  isActive,
  displayTitle,
  onActivate,
  onClose,
  onContextMenu,
}: SortableTabItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tab.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    flex: "1 1 auto",
    minWidth: TAB_MIN_WIDTH,
    maxWidth: TAB_MAX_WIDTH,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Flex
        align="center"
        justify="between"
        px="3"
        onClick={onActivate}
        onContextMenu={onContextMenu}
        style={{
          width: "100%",
          height: isActive ? 33 : 30,
          cursor: isDragging ? "grabbing" : "pointer",
          background: isActive ? "var(--color-background)" : "var(--gray-a2)",
          borderTop: "1px solid var(--gray-a4)",
          borderLeft: "1px solid var(--gray-a4)",
          borderRight: "1px solid var(--gray-a4)",
          borderBottom: isActive ? "1px solid var(--color-background)" : "none",
          borderTopLeftRadius: "var(--radius-2)",
          borderTopRightRadius: "var(--radius-2)",
          userSelect: "none",
          position: "relative",
          zIndex: isActive ? 2 : 0,
          marginBottom: isActive ? 0 : 1,
        }}
        >
          {/* 类型图标 */}
          {tab.type === "chapter" ? (
            <FileText size={12} style={{ flexShrink: 0, marginRight: 4, opacity: 0.6 }} />
          ) : (
            <StickyNote size={12} style={{ flexShrink: 0, marginRight: 4, opacity: 0.6 }} />
          )}
          {/* 标题 */}
        <Text
          size="2"
          weight={isActive ? "medium" : "regular"}
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            flex: 1,
            color: isActive ? "var(--gray-12)" : "var(--gray-11)",
          }}
        >
          {displayTitle}
        </Text>

        {/* 关闭按钮（右侧） */}
        {!tab.isLocked && (
          <IconButton
            variant="ghost"
            size="1"
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            style={{
              width: 18,
              height: 18,
              minWidth: 18,
              minHeight: 18,
              flexShrink: 0,
              marginLeft: 4,
            }}
          >
            <X size={12} />
          </IconButton>
        )}
      </Flex>
    </div>
  );
});

/** 空标签页内容 */
interface EmptyTabContentProps {
  onCreateNew: () => void;
  onClose: () => void;
}

export function EmptyTabContent({
  onCreateNew,
  onClose,
}: EmptyTabContentProps) {
  const { t } = useTranslation();

  return (
    <Flex
      align="center"
      justify="center"
      direction="column"
      gap="4"
      style={{ height: "100%", minHeight: 400 }}
    >
      <Flex gap="3">
        <Button variant="soft" size="2" onClick={onCreateNew}>
          <FilePlus size={16} />
          {t("tabs.createNewFile")}
        </Button>
        <Button variant="soft" color="gray" size="2" onClick={onClose}>
          <XCircle size={16} />
          {t("tabs.closeFile")}
        </Button>
      </Flex>
    </Flex>
  );
}

interface EditorTabsProps {
  onAddTab?: () => void;
  onAddToConversation?: (markup: string) => void;
}

export function EditorTabs({ onAddTab, onAddToConversation }: EditorTabsProps) {
  const { t } = useTranslation();
  const tabs = useTabs();
  const activeTabId = useActiveTabId();
  const { setActiveTab, closeTab, reorderTabs, closeOtherTabs, closeAllTabs, toggleLock } = useTabsStore();

  // 拖拽传感器
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

  // 右键菜单状态
  const [contextMenuPos, setContextMenuPos] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [contextMenuTabId, setContextMenuTabId] = useState<string | null>(null);

  // 激活标签页
  const handleActivate = useCallback(
    (tabId: string) => {
      setActiveTab(tabId);
    },
    [setActiveTab]
  );

  // 关闭标签页
  const handleClose = useCallback(
    (tabId: string) => {
      closeTab(tabId);
    },
    [closeTab]
  );

  // 打开右键菜单
  const handleContextMenu = useCallback(
    (tabId: string, e: React.MouseEvent) => {
      e.preventDefault();
      setContextMenuTabId(tabId);
      setContextMenuPos({ x: e.clientX, y: e.clientY });
    },
    []
  );

  // 关闭右键菜单
  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuTabId(null);
  }, []);

  // 新建标签页
  const handleAddTab = useCallback(() => {
    onAddTab?.();
  }, [onAddTab]);

  // 拖拽结束
  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (over && active.id !== over.id) {
        reorderTabs(active.id as string, over.id as string);
      }
    },
    [reorderTabs]
  );

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuTabId) return [];
    const targetTab = tabs.find((tab) => tab.id === contextMenuTabId);
    if (!targetTab) return [];

    const items: ContextMenuItem[] = [];
    if (targetTab.refId) {
      items.push({
        id: "addToConversation",
        label: t("tabs.addToConversation"),
        icon: AtSign,
        disabled: !onAddToConversation,
        onClick: () => {
          if (targetTab.type === "note") {
            onAddToConversation?.(buildNoteMentionTag({
              noteId: targetTab.refId!,
              label: targetTab.title.trim() || t("writing.untitledNote"),
            }));
          } else {
            onAddToConversation?.(buildChapterMentionTag({
              chapterId: targetTab.refId!,
              label: targetTab.title.trim() || t("writing.untitledChapter"),
            }));
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
  }, [closeAllTabs, closeOtherTabs, closeTab, contextMenuTabId, onAddToConversation, t, tabs, toggleLock]);

  return (
    <>
      <Box
        style={{
          background: "var(--gray-a2)",
          position: "relative",
        }}
      >
        {/* 底部边框线 - 位于标签页下方 */}
        <Box
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 1,
            background: "var(--gray-a4)",
            zIndex: 0,
          }}
        />
        <Flex
          align="end"
          gap="0"
          px="2"
          style={{ height: 34, position: "relative", zIndex: 1 }}
        >
          {/* 标签页列表和添加按钮 */}
          <Flex
            gap="1"
            align="end"
            style={{
              flex: 1,
              overflow: "hidden",
            }}
          >
            {/* 标签页拖拽区域 - 使用 flex 布局自动压缩 */}
            <Flex
              gap="1"
              align="end"
              style={{
                minWidth: 0,
                overflow: "hidden",
              }}
            >
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                modifiers={[restrictToHorizontalAxis, restrictToParentElement]}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={tabs.map((t) => t.id)}
                  strategy={horizontalListSortingStrategy}
                >
                  {tabs.map((tab) => (
                    <SortableTabItem
                      key={tab.id}
                      tab={tab}
                      isActive={tab.id === activeTabId}
                      displayTitle={
                        isEmptyTab(tab.id) ? t("tabs.emptyTab") : tab.title
                      }
                      onActivate={() => handleActivate(tab.id)}
                      onClose={() => handleClose(tab.id)}
                      onContextMenu={(e) => handleContextMenu(tab.id, e)}
                    />
                  ))}
                </SortableContext>
              </DndContext>
            </Flex>

            {/* 添加按钮 - 紧跟在标签页后方 */}
            <IconButton
              variant="ghost"
              size="1"
              onClick={handleAddTab}
              style={{
                width: 28,
                height: 28,
                marginBottom: 2,
                flexShrink: 0,
              }}
            >
              <Plus size={16} />
            </IconButton>
          </Flex>
        </Flex>
      </Box>

      {/* 标签页右键菜单 */}
      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />
    </>
  );
}
