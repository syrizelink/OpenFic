const AUTO_SCROLL_EDGE_THRESHOLD = 56;
const AUTO_SCROLL_MAX_SPEED = 18;

export const CHAPTER_LIST_ITEM_HEIGHT = 64;

interface AutoScrollPosition {
  containerTop: number;
  containerBottom: number;
  itemTop: number;
  itemBottom: number;
}

interface ChapterDragTargetPosition {
  containerTop: number;
  scrollTop: number;
  clientY: number;
  groupContentTop: number;
  itemCount: number;
}

interface ChapterDragGroupContentTopPosition {
  containerTop: number;
  scrollTop: number;
  initialTop: number | null;
  activeIndex: number;
}

interface ChapterDragOffsetPosition {
  chapterIndex: number;
  activeIndex: number;
  targetIndex: number;
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

export function getChapterDragGroupContentTop({
  containerTop,
  scrollTop,
  initialTop,
  activeIndex,
}: ChapterDragGroupContentTopPosition): number | null {
  if (initialTop === null) return null;

  return scrollTop + initialTop - containerTop - activeIndex * CHAPTER_LIST_ITEM_HEIGHT;
}

export function getChapterDragTargetIndex({
  containerTop,
  scrollTop,
  clientY,
  groupContentTop,
  itemCount,
}: ChapterDragTargetPosition): number {
  if (itemCount <= 1) return 0;

  const index = Math.floor(
    (scrollTop + clientY - containerTop - groupContentTop) / CHAPTER_LIST_ITEM_HEIGHT,
  );
  return Math.max(0, Math.min(index, itemCount - 1));
}

export function getChapterDragOffset({
  chapterIndex,
  activeIndex,
  targetIndex,
}: ChapterDragOffsetPosition): number {
  if (chapterIndex === activeIndex || activeIndex === targetIndex) return 0;

  if (activeIndex < targetIndex && chapterIndex > activeIndex && chapterIndex <= targetIndex) {
    return -CHAPTER_LIST_ITEM_HEIGHT;
  }

  if (activeIndex > targetIndex && chapterIndex >= targetIndex && chapterIndex < activeIndex) {
    return CHAPTER_LIST_ITEM_HEIGHT;
  }

  return 0;
}

export function reorderChapterIds(
  chapterIds: string[],
  fromIndex: number,
  toIndex: number,
): string[] | null {
  if (
    fromIndex < 0 ||
    fromIndex >= chapterIds.length ||
    toIndex < 0 ||
    toIndex >= chapterIds.length ||
    fromIndex === toIndex
  ) {
    return null;
  }

  const reorderedIds = [...chapterIds];
  const [movedId] = reorderedIds.splice(fromIndex, 1);
  reorderedIds.splice(toIndex, 0, movedId);
  return reorderedIds;
}
