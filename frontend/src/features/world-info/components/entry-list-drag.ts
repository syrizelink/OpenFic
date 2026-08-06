const AUTO_SCROLL_EDGE_THRESHOLD = 56;
const AUTO_SCROLL_MAX_SPEED = 18;
export const ENTRY_LIST_ITEM_HEIGHT = 69;

interface AutoScrollPosition {
  containerTop: number;
  containerBottom: number;
  itemTop: number;
  itemBottom: number;
}

interface DragTargetPosition {
  containerTop: number;
  scrollTop: number;
  clientY: number;
  itemCount: number;
}

interface SortableEntry {
  id: string;
  order: number;
}

interface EntryDragOffsetPosition {
  entryIndex: number;
  activeIndex: number;
  targetIndex: number;
}

interface DragVisibilityState {
  isDragSource: boolean;
}

export function getAutoScrollSpeed({
  containerTop,
  containerBottom,
  itemTop,
  itemBottom,
}: AutoScrollPosition): number {
  const distanceToTop = itemTop - containerTop;
  if (distanceToTop < AUTO_SCROLL_EDGE_THRESHOLD) {
    const ratio = (AUTO_SCROLL_EDGE_THRESHOLD - distanceToTop) / AUTO_SCROLL_EDGE_THRESHOLD;
    return -Math.max(4, Math.round(AUTO_SCROLL_MAX_SPEED * ratio));
  }

  const distanceToBottom = containerBottom - itemBottom;
  if (distanceToBottom < AUTO_SCROLL_EDGE_THRESHOLD) {
    const ratio = (AUTO_SCROLL_EDGE_THRESHOLD - distanceToBottom) / AUTO_SCROLL_EDGE_THRESHOLD;
    return Math.max(4, Math.round(AUTO_SCROLL_MAX_SPEED * ratio));
  }

  return 0;
}

export function getDragTargetIndex({
  containerTop,
  scrollTop,
  clientY,
  itemCount,
}: DragTargetPosition): number {
  if (itemCount <= 1) return 0;

  const index = Math.floor((scrollTop + clientY - containerTop) / ENTRY_LIST_ITEM_HEIGHT);
  return Math.max(0, Math.min(index, itemCount - 1));
}

export function reorderEntries<T extends SortableEntry>(
  entries: T[],
  activeId: string,
  newIndex: number,
): T[] | null {
  const oldIndex = entries.findIndex((entry) => entry.id === activeId);
  if (oldIndex === -1 || oldIndex === newIndex) return null;

  const reordered = [...entries];
  const [movedEntry] = reordered.splice(oldIndex, 1);
  reordered.splice(newIndex, 0, movedEntry);
  return reordered.map((entry, index) => ({ ...entry, order: index + 1 }));
}

export function getEntryDragOffset({
  entryIndex,
  activeIndex,
  targetIndex,
}: EntryDragOffsetPosition): number {
  if (entryIndex === activeIndex || activeIndex === targetIndex) return 0;

  if (activeIndex < targetIndex && entryIndex > activeIndex && entryIndex <= targetIndex) {
    return -ENTRY_LIST_ITEM_HEIGHT;
  }

  if (activeIndex > targetIndex && entryIndex >= targetIndex && entryIndex < activeIndex) {
    return ENTRY_LIST_ITEM_HEIGHT;
  }

  return 0;
}

export function shouldHideDraggedEntry({ isDragSource }: DragVisibilityState): boolean {
  return isDragSource;
}

export function getEntryListTransition(isDragActive: boolean): string {
  if (isDragActive) {
    return "transform 0.14s ease, background-color 0.08s ease, color 0.08s ease";
  }
  return "background-color 0.08s ease, color 0.08s ease";
}
