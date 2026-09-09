import type { ChapterListItem, VolumeWithChapters } from "@/lib/chapter.types";

export type GroupedVolumeListItem =
  | {
      type: "chapter";
      key: string;
      volumeId: string;
      chapter: ChapterListItem;
    }
  | {
      type: "empty";
      key: string;
      volumeId: string;
    };

interface BuildGroupedVolumeListModelParams {
  volumes: VolumeWithChapters[];
  expandedVolumeIds: Set<string>;
  chapterOrderMap?: Readonly<Record<string, number>>;
}

interface GetCollapseScrollGroupIndexParams {
  volumes: VolumeWithChapters[];
  expandedVolumeIds: Set<string>;
  volumeId: string;
}

interface ShouldAnchorCollapsedGroupScrollParams {
  groupIndex: number;
  stickyGroupIndex?: number;
  groupTop?: number;
  viewportTop: number;
}

export interface GroupedVolumeListModel {
  items: GroupedVolumeListItem[];
  groupCounts: number[];
  chapterById: Map<string, ChapterListItem>;
  chapterIndexById: Map<string, number>;
  keyByInternalIndex: Map<number, string>;
  getChapterScrollIndex: (chapterId: string) => number | undefined;
}

export function getCollapseScrollGroupIndex({
  volumes,
  expandedVolumeIds,
  volumeId,
}: GetCollapseScrollGroupIndexParams): number | undefined {
  if (!expandedVolumeIds.has(volumeId)) {
    return undefined;
  }

  const groupIndex = volumes.findIndex((volume) => volume.id === volumeId);
  return groupIndex >= 0 ? groupIndex : undefined;
}

export function shouldAnchorCollapsedGroupScroll({
  groupIndex,
  stickyGroupIndex,
  groupTop,
  viewportTop,
}: ShouldAnchorCollapsedGroupScrollParams): boolean {
  if (groupIndex === 0) {
    return true;
  }

  if (stickyGroupIndex === groupIndex) {
    return true;
  }

  return typeof groupTop === "number" && groupTop <= viewportTop;
}

export function getSortedVolumeChapters(
  chapters: ChapterListItem[],
  dragOrderMap?: Readonly<Record<string, number>>,
): ChapterListItem[] {
  if (!dragOrderMap || Object.keys(dragOrderMap).length === 0) {
    return chapters;
  }

  return [...chapters].sort((a, b) => {
    const orderA = dragOrderMap[a.id] ?? a.order;
    const orderB = dragOrderMap[b.id] ?? b.order;
    return orderA - orderB;
  });
}

export function getGroupedVolumeListStructureSignature(
  volumes: VolumeWithChapters[],
  expandedVolumeIds: Set<string>,
): string {
  return volumes
    .map((volume) => {
      const isExpanded = expandedVolumeIds.has(volume.id);
      const chapterSignature = isExpanded
        ? volume.chapters.map((chapter) => chapter.id).join(",")
        : String(volume.chapterCount);

      return `${volume.id}:${isExpanded ? "expanded" : "collapsed"}:${chapterSignature}`;
    })
    .join("|");
}

export function buildGroupedVolumeListModel({
  volumes,
  expandedVolumeIds,
  chapterOrderMap,
}: BuildGroupedVolumeListModelParams): GroupedVolumeListModel {
  const items: GroupedVolumeListItem[] = [];
  const groupCounts: number[] = [];
  const chapterById = new Map<string, ChapterListItem>();
  const chapterIndexById = new Map<string, number>();
  const chapterScrollIndexById = new Map<string, number>();
  const keyByInternalIndex = new Map<number, string>();
  let itemIndex = 0;
  let internalIndex = 0;

  for (const volume of volumes) {
    const chapters = getSortedVolumeChapters(volume.chapters, chapterOrderMap);

    keyByInternalIndex.set(internalIndex, `volume:${volume.id}`);
    internalIndex += 1;

    for (const chapter of volume.chapters) {
      chapterById.set(chapter.id, chapter);
    }

    if (!expandedVolumeIds.has(volume.id)) {
      groupCounts.push(0);
      continue;
    }

    if (chapters.length === 0) {
      items.push({
        type: "empty",
        key: `empty:${volume.id}`,
        volumeId: volume.id,
      });
      keyByInternalIndex.set(internalIndex, `empty:${volume.id}`);
      groupCounts.push(1);
      internalIndex += 1;
      itemIndex += 1;
      continue;
    }

    groupCounts.push(chapters.length);
    for (const [chapterIndex, chapter] of chapters.entries()) {
      items.push({
        type: "chapter",
        key: `chapter:${chapter.id}`,
        volumeId: volume.id,
        chapter,
      });
      chapterIndexById.set(chapter.id, chapterIndex);
      keyByInternalIndex.set(internalIndex, `chapter:${chapter.id}`);
      chapterScrollIndexById.set(chapter.id, itemIndex);
      internalIndex += 1;
      itemIndex += 1;
    }
  }

  return {
    items,
    groupCounts,
    chapterById,
    chapterIndexById,
    keyByInternalIndex,
    getChapterScrollIndex: (chapterId) => chapterScrollIndexById.get(chapterId),
  };
}
