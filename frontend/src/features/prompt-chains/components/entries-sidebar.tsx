/**
 * EntriesSidebar Component
 *
 * 左侧边栏：提示词条目列表
 */

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis, restrictToParentElement } from "@dnd-kit/modifiers";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Box, Flex, Text, IconButton, Switch } from "@radix-ui/themes";
import { GripVertical, Trash2, User, Bot, Terminal } from "lucide-react";
import React, { useRef } from "react";
import { useTranslation } from "react-i18next";

import type { PromptEntryData } from "@/lib/prompt-chain.types";

import { EntriesToolbar } from "./entries-toolbar";

interface EntriesSidebarProps {
  entries: PromptEntryData[];
  selectedEntryId: string | null;
  onSelectEntry: (entryId: string) => void;
  onToggleEntry: (entryId: string) => void;
  onDeleteEntry: (entryId: string) => void;
  onReorderEntries: (entries: PromptEntryData[]) => void;
  onCreateEntry: () => void;
  highlightEntryId: string | null;
}

export function EntriesSidebar({
  entries,
  selectedEntryId,
  onSelectEntry,
  onToggleEntry,
  onDeleteEntry,
  onReorderEntries,
  onCreateEntry,
  highlightEntryId,
}: EntriesSidebarProps) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLDivElement>(null);
  const entryRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = entries.findIndex((e) => e.id === active.id);
      const newIndex = entries.findIndex((e) => e.id === over.id);

      const reordered = arrayMove(entries, oldIndex, newIndex).map((e, idx) => ({
        ...e,
        order_index: idx,
      }));
      onReorderEntries(reordered);
    }
  };

  // 滚动到选中的条目
  const handleSelectWithScroll = (entryId: string) => {
    onSelectEntry(entryId);
    const entryElement = entryRefs.current.get(entryId);
    if (entryElement && listRef.current) {
      entryElement.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  };

  // 如果没有条目，显示空状态
  if (entries.length === 0) {
    return (
      <Box
        style={{
          borderRight: "1px solid var(--gray-a5)",
          background: "var(--color-background)",
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <EntriesToolbar
          entries={entries}
          onEntrySelect={handleSelectWithScroll}
          onCreateEntry={onCreateEntry}
        />
        <Box
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
          }}
        >
          <Text
            size="2"
            color="gray"
            align="center"
          >
            {t("promptChains.selectModeAndTask")}
          </Text>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      style={{
        height: "100%",
        borderRight: "1px solid var(--gray-a5)",
        background: "var(--color-background)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* 工具栏 */}
      <EntriesToolbar
        entries={entries}
        onEntrySelect={handleSelectWithScroll}
        onCreateEntry={onCreateEntry}
      />

      {/* 条目列表 */}
      <Box
        ref={listRef}
        style={{ flex: 1, overflow: "auto" }}
      >
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
          modifiers={[restrictToVerticalAxis, restrictToParentElement]}
          autoScroll={false}
        >
          <SortableContext
            items={entries.map((e) => e.id || "")}
            strategy={verticalListSortingStrategy}
          >
            {entries.map((entry) => (
              <EntryItem
                key={entry.id}
                entry={entry}
                isSelected={entry.id === selectedEntryId}
                isHighlighted={entry.id === highlightEntryId}
                onSelect={() => entry.id && onSelectEntry(entry.id)}
                onToggle={() => entry.id && onToggleEntry(entry.id)}
                onDelete={() => entry.id && onDeleteEntry(entry.id)}
                ref={(el) => {
                  if (el && entry.id) {
                    entryRefs.current.set(entry.id, el);
                  }
                }}
              />
            ))}
          </SortableContext>
        </DndContext>
      </Box>
    </Box>
  );
}

interface EntryItemProps {
  entry: PromptEntryData;
  isSelected: boolean;
  isHighlighted: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onDelete: () => void;
}

const EntryItem = React.forwardRef<HTMLDivElement, EntryItemProps>(
  ({ entry, isSelected, isHighlighted, onSelect, onToggle, onDelete }, ref) => {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
      id: entry.id || "",
    });

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
      opacity: isDragging ? 0.5 : 1,
    };

    // 角色图标
    const RoleIcon = entry.role === "system" ? Terminal : entry.role === "assistant" ? Bot : User;

    // 合并 refs
    const combinedRef = (node: HTMLDivElement | null) => {
      setNodeRef(node);
      if (typeof ref === "function") {
        ref(node);
      } else if (ref) {
        ref.current = node;
      }
    };

    return (
      <Box
        ref={combinedRef}
        className={isHighlighted && !isSelected ? "entry-highlight" : ""}
        style={{
          ...style,
          borderBottom: "1px solid var(--gray-a5)",
          background: isSelected ? "var(--accent-a3)" : "transparent",
          cursor: "pointer",
          width: "100%",
          minWidth: 0,
          overflow: "hidden",
          touchAction: isDragging ? "none" : "pan-y",
          userSelect: "none",
          WebkitUserSelect: "none",
          WebkitTouchCallout: "none",
          WebkitTapHighlightColor: "transparent",
        }}
        onContextMenu={(e) => e.preventDefault()}
        onClick={onSelect}
      >
        <Flex
          align="stretch"
          justify="between"
          style={{ minWidth: 0, width: "100%" }}
        >
          <Flex
            {...attributes}
            {...listeners}
            align="center"
            justify="center"
            style={{
              width: 44,
              minWidth: 44,
              flexShrink: 0,
              cursor: isDragging ? "grabbing" : "grab",
              color: "var(--gray-a9)",
              touchAction: "none",
              userSelect: "none",
              WebkitUserSelect: "none",
            }}
            onClick={(e) => e.stopPropagation()}
            onContextMenu={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            <GripVertical size={16} />
          </Flex>

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
              align="center"
              gap="2"
              style={{ flex: 1, minWidth: 0 }}
            >
              <Box style={{ color: "var(--gray-a10)", flexShrink: 0 }}>
                <RoleIcon size={14} />
              </Box>

              <Text
                size="2"
                weight="medium"
                style={{
                  flex: 1,
                  minWidth: 0,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {entry.name}
              </Text>
            </Flex>

            <Flex
              align="center"
              gap="1"
              style={{ flexShrink: 0 }}
            >
              {/* 删除按钮 */}
              <IconButton
                variant="ghost"
                size="1"
                color="red"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
              >
                <Trash2 size={12} />
              </IconButton>

              {/* 启用开关 */}
              <Switch
                size="1"
                checked={entry.is_enabled}
                onClick={(e) => e.stopPropagation()}
                onCheckedChange={onToggle}
              />

              {/* Token计数（只显示数字） */}
              <Text
                size="1"
                color="gray"
                style={{ minWidth: "32px", textAlign: "right" }}
              >
                {entry.token_count}
              </Text>
            </Flex>
          </Flex>
        </Flex>

        {/* 闪烁动画样式 */}
        {!isSelected && (
          <style>{`
          .entry-highlight {
            animation: highlight-flash 1s ease-out;
          }
          
          @keyframes highlight-flash {
            0%, 100% {
              background: transparent;
            }
            50% {
              background: var(--accent-a5);
            }
          }
        `}</style>
        )}
      </Box>
    );
  },
);

EntryItem.displayName = "EntryItem";
