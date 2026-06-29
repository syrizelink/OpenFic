import { useMemo, useCallback } from "react";
import { Flex, Text } from "@radix-ui/themes";
import * as DndKitCore from "@dnd-kit/core";
import { toast } from "@/components";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";
import {
  DndContext,
  useSensor,
  useSensors,
  useDroppable,
  pointerWithin,
  type DragEndEvent,
  type CollisionDetection,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";

import { NoteTreeItem, type NoteTreeItemData } from "./note-tree-item";
import { useNotesStore } from "../store/use-notes-store";
import type { NoteTreeResponse, NoteCategoryItem, NoteListItem } from "@/lib/note.types";

const ROOT_DROP_ID = "note-tree-root";

interface NoteTreeProps {
  data: NoteTreeResponse | undefined;
  onNoteSelect: (noteId: string, title: string) => void;
  onCategorySelect: (categoryId: string) => void;
  currentNoteId: string | null;
  selectedCategoryId: string | null;
  renamingId: string | null;
  onRenameConfirm: (id: string, type: "category" | "note", newTitle: string) => void;
  onRenameCancel: () => void;
  onContextMenu: (id: string, type: "category" | "note", position: { x: number; y: number }, title: string) => void;
  onMove: (itemId: string, kind: "category" | "note", targetCategoryId: string | null) => Promise<void>;
}

function flattenTree(
  categories: NoteCategoryItem[],
  notes: NoteListItem[],
  expandedIds: Set<string>,
  depth: number,
  parentId: string | null,
  ancestorCategoryIds: string[],
): NoteTreeItemData[] {
  const result: NoteTreeItemData[] = [];

  for (const cat of categories) {
    const isExpanded = expandedIds.has(cat.id);
    result.push({
      type: "category",
      id: cat.id,
      title: cat.title,
      parentId: cat.parentId,
      depth,
      isExpanded,
      childCount: cat.categories.length + cat.notes.length,
      ancestorCategoryIds,
    });

    if (isExpanded) {
      result.push(
        ...flattenTree(
          cat.categories,
          cat.notes,
          expandedIds,
          depth + 1,
          cat.id,
          [...ancestorCategoryIds, cat.id],
        ),
      );
    }
  }

  for (const note of notes) {
    result.push({
      type: "note",
      id: note.id,
      title: note.title,
      parentId,
      depth,
      isLocked: note.isLocked,
      isHidden: note.isHidden,
      ancestorCategoryIds,
    });
  }

  return result;
}

function buildCategoryParentMap(
  categories: NoteCategoryItem[],
): Map<string, string | null> {
  const map = new Map<string, string | null>();
  const walk = (cats: NoteCategoryItem[]) => {
    for (const cat of cats) {
      map.set(cat.id, cat.parentId);
      walk(cat.categories);
    }
  };
  walk(categories);
  return map;
}

function findNoteCategoryId(
  data: NoteTreeResponse,
  noteId: string,
): string | null {
  const walk = (cats: NoteCategoryItem[]): string | null => {
    for (const cat of cats) {
      const found = cat.notes.find((n) => n.id === noteId);
      if (found) return found.categoryId;
      const nested = walk(cat.categories);
      if (nested !== null) return nested;
    }
    return null;
  };
  const fromCategory = walk(data.categories);
  if (fromCategory !== null) return fromCategory;
  return data.rootNotes.find((n) => n.id === noteId)?.categoryId ?? null;
}

function computeActiveAncestorIds(
  data: NoteTreeResponse,
  noteId: string | null,
): Set<string> {
  if (!noteId) return new Set();
  const categoryId = findNoteCategoryId(data, noteId);
  if (!categoryId) return new Set();

  const parentMap = buildCategoryParentMap(data.categories);
  const chain = new Set<string>();
  let current: string | null = categoryId;
  while (current) {
    chain.add(current);
    current = parentMap.get(current) ?? null;
  }
  return chain;
}

function canAcceptDrop(
  sourceType: "category" | "note",
  targetType: "category" | "droppable_root",
  targetDepth: number,
): boolean {
  if (sourceType === "note" && targetType === "category" && targetDepth >= 2) {
    return false;
  }

  if (sourceType === "category" && targetType === "category" && targetDepth >= 1) {
    return false;
  }

  return true;
}

function isDescendantOf(
  categories: NoteCategoryItem[],
  parentId: string,
  targetId: string,
): boolean {
  for (const cat of categories) {
    if (cat.id === targetId) {
      if (parentId === cat.id) return true;
      return isDescendantOf(cat.categories, parentId, targetId);
    }
    if (isDescendantOf(cat.categories, parentId, targetId)) return true;
  }
  return false;
}

function createCollisionDetection(): CollisionDetection {
  return (args) => {
    const collisions = pointerWithin(args);
    if (collisions.length <= 1) return collisions;

    const nonRoot = collisions.filter((c) => c.id !== ROOT_DROP_ID);
    if (nonRoot.length > 0) return nonRoot;
    return collisions;
  };
}

function RootDropArea({ children }: { children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: ROOT_DROP_ID });

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: "auto",
        overflowX: "hidden",
        boxShadow: isOver ? "inset 0 0 0 1px var(--accent-a5)" : undefined,
        borderRadius: 6,
      }}
    >
      {children}
    </div>
  );
}

export function NoteTree({
  data,
  onNoteSelect,
  onCategorySelect,
  currentNoteId,
  selectedCategoryId,
  renamingId,
  onRenameConfirm,
  onRenameCancel,
  onContextMenu,
  onMove,
}: NoteTreeProps) {
  const { t } = useTranslation();
  const [expandedIds, toggleExpanded] = useNotesStore(
    useShallow((s) => [s.expandedNoteCategoryIds, s.toggleNoteCategoryExpanded])
  );

  const sensors = useSensors(
    useSensor(DndKitCore.MouseSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(DndKitCore.TouchSensor, {
      activationConstraint: { delay: 280, tolerance: 8 },
    })
  );

  const collisionDetection = useMemo(
    () => createCollisionDetection(),
    []
  );

  const handleSelect = useCallback(
    (id: string, itemType: "category" | "note") => {
      if (itemType === "note") {
        const noteData = data?.rootNotes.find((n) => n.id === id)
          || findNoteInCategories(data?.categories ?? [], id);
        onNoteSelect(id, noteData?.title ?? "");
      } else {
        onCategorySelect(id);
      }
    },
    [data, onNoteSelect, onCategorySelect]
  );

  const handleExpand = useCallback(
    (id: string) => {
      toggleExpanded(id);
    },
    [toggleExpanded]
  );

  const activeAncestorCategoryIds = useMemo(
    () => (data ? computeActiveAncestorIds(data, currentNoteId) : new Set<string>()),
    [data, currentNoteId],
  );

  const flatItems = useMemo(() => {
    if (!data) return [];
    return flattenTree(data.categories, data.rootNotes, expandedIds, 0, null, []);
  }, [data, expandedIds]);
  const isEmpty = !!data && flatItems.length === 0;

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over) return;

      const activeData = active.data.current as {
        itemType: string;
        itemId: string;
        depth: number;
        parentId?: string | null;
      } | undefined;
      const overData = over.data.current as { itemType?: string; itemId?: string; depth?: number } | undefined;

      if (!activeData) return;

      const sourceKind = activeData.itemType as "category" | "note";
      const sourceId = activeData.itemId;

      let targetCategoryId: string | null = null;

      if (over.id === ROOT_DROP_ID) {
        targetCategoryId = null;
        if (!canAcceptDrop(sourceKind, "droppable_root", 0)) {
          toast.error(t("writing.categoryDepthExceeded"));
          return;
        }
      } else if (overData?.itemType === "category") {
        if (sourceKind === "category" && overData.itemId === sourceId) {
          return;
        }
        targetCategoryId = overData.itemId!;
        const targetDepth = overData.depth ?? 0;

        if (sourceKind === "category"
          && data?.categories
          && isDescendantOf(data.categories, sourceId, targetCategoryId)
        ) {
          toast.error(t("writing.cannotMoveIntoDescendant"));
          return;
        }

        if (!canAcceptDrop(sourceKind, "category", targetDepth)) {
          toast.error(t("writing.categoryDepthExceeded"));
          return;
        }
      } else {
        return;
      }

      if ((activeData.parentId ?? null) === targetCategoryId) {
        return;
      }

      onMove(sourceId, sourceKind, targetCategoryId).catch(() => {
        // error handled by mutation
      });
    },
    [onMove, t, data]
  );

  if (!data) return null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragEnd={handleDragEnd}
      modifiers={[restrictToVerticalAxis]}
    >
      <RootDropArea>
        {isEmpty ? (
          <Flex align="center" justify="center" p="6" style={{ minHeight: "100%" }}>
            <Text size="2" color="gray" align="center">
              {t("writing.emptyNotes")}
            </Text>
          </Flex>
        ) : (
          flatItems.map((item) => (
            <NoteTreeItem
              key={`${item.type}:${item.id}`}
              data={item}
              isActive={
                (item.type === "note" && item.id === currentNoteId) ||
                (item.type === "category" && item.id === selectedCategoryId)
              }
              isRenaming={renamingId === `${item.type}:${item.id}`}
              activeAncestorCategoryIds={activeAncestorCategoryIds}
              onSelect={handleSelect}
              onExpand={handleExpand}
              onContextMenu={onContextMenu}
              onRenameConfirm={onRenameConfirm}
              onRenameCancel={onRenameCancel}
            />
          ))
        )}
      </RootDropArea>
    </DndContext>
  );
}

function findNoteInCategories(categories: NoteCategoryItem[], noteId: string): NoteListItem | undefined {
  for (const cat of categories) {
    const found = cat.notes.find((n) => n.id === noteId);
    if (found) return found;
    const nested = findNoteInCategories(cat.categories, noteId);
    if (nested) return nested;
  }
  return undefined;
}
