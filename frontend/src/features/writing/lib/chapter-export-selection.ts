import type { VolumeWithChapters } from "@/lib/chapter.types";

export interface ChapterExportSelection {
  selectedVolumeIds: Set<string>;
  includedChapterIds: Set<string>;
  excludedChapterIds: Set<string>;
  lastChapterAnchorId: string | null;
}

export type ChapterExportCheckState = "unchecked" | "indeterminate" | "checked";

export function createChapterExportSelection(): ChapterExportSelection {
  return {
    selectedVolumeIds: new Set(),
    includedChapterIds: new Set(),
    excludedChapterIds: new Set(),
    lastChapterAnchorId: null,
  };
}

export function getExportableVolumes(volumes: VolumeWithChapters[]): VolumeWithChapters[] {
  return volumes.filter((volume) => volume.chapters.length > 0);
}

export function getSelectedChapterIds(
  volumes: VolumeWithChapters[],
  selection: ChapterExportSelection,
): Set<string> {
  const availableChapterIds = new Set(
    volumes.flatMap((volume) => volume.chapters.map((chapter) => chapter.id)),
  );
  const selected = new Set(
    [...selection.includedChapterIds].filter((chapterId) => availableChapterIds.has(chapterId)),
  );
  for (const volume of volumes) {
    if (!selection.selectedVolumeIds.has(volume.id)) continue;
    for (const chapter of volume.chapters) selected.add(chapter.id);
  }
  for (const chapterId of selection.excludedChapterIds) selected.delete(chapterId);
  return selected;
}

export function getVolumeCheckState(
  volume: VolumeWithChapters,
  selectedChapterIds: Set<string>,
): ChapterExportCheckState {
  const selectedCount = volume.chapters.filter((chapter) =>
    selectedChapterIds.has(chapter.id),
  ).length;
  if (selectedCount === 0) return "unchecked";
  return selectedCount === volume.chapters.length ? "checked" : "indeterminate";
}

export function getProjectCheckState(
  volumes: VolumeWithChapters[],
  selectedChapterIds: Set<string>,
): ChapterExportCheckState {
  const chapters = volumes.flatMap((volume) => volume.chapters);
  if (chapters.length === 0) return "unchecked";
  const selectedCount = chapters.filter((chapter) => selectedChapterIds.has(chapter.id)).length;
  if (selectedCount === 0) return "unchecked";
  return selectedCount === chapters.length ? "checked" : "indeterminate";
}

export function toggleVolumeSelection(
  selection: ChapterExportSelection,
  volume: VolumeWithChapters,
  state: ChapterExportCheckState,
): ChapterExportSelection {
  const next = copySelection(selection);
  if (state === "checked") {
    next.selectedVolumeIds.delete(volume.id);
    volume.chapters.forEach((chapter) => {
      next.includedChapterIds.delete(chapter.id);
      next.excludedChapterIds.delete(chapter.id);
    });
    return next;
  }

  next.selectedVolumeIds.add(volume.id);
  volume.chapters.forEach((chapter) => {
    next.includedChapterIds.delete(chapter.id);
    next.excludedChapterIds.delete(chapter.id);
  });
  return next;
}

export function toggleProjectSelection(
  volumes: VolumeWithChapters[],
  state: ChapterExportCheckState,
): ChapterExportSelection {
  if (state === "checked") return createChapterExportSelection();

  return {
    selectedVolumeIds: new Set(volumes.map((volume) => volume.id)),
    includedChapterIds: new Set(),
    excludedChapterIds: new Set(),
    lastChapterAnchorId: null,
  };
}

export function toggleChapterSelection(
  selection: ChapterExportSelection,
  volumes: VolumeWithChapters[],
  chapterId: string,
): ChapterExportSelection {
  const selectedChapterIds = getSelectedChapterIds(volumes, selection);
  return applyChapterSelection(
    selection,
    volumes,
    [chapterId],
    !selectedChapterIds.has(chapterId),
    chapterId,
  );
}

export function toggleChapterRangeSelection(
  selection: ChapterExportSelection,
  volumes: VolumeWithChapters[],
  chapterId: string,
): ChapterExportSelection {
  const orderedChapterIds = volumes.flatMap((volume) =>
    volume.chapters.map((chapter) => chapter.id),
  );
  const anchorIndex = selection.lastChapterAnchorId
    ? orderedChapterIds.indexOf(selection.lastChapterAnchorId)
    : -1;
  const targetIndex = orderedChapterIds.indexOf(chapterId);
  if (anchorIndex === -1 || targetIndex === -1) {
    return toggleChapterSelection(selection, volumes, chapterId);
  }

  const start = Math.min(anchorIndex, targetIndex);
  const end = Math.max(anchorIndex, targetIndex);
  const selectedChapterIds = getSelectedChapterIds(volumes, selection);
  return applyChapterSelection(
    selection,
    volumes,
    orderedChapterIds.slice(start, end + 1),
    !selectedChapterIds.has(chapterId),
    chapterId,
  );
}

function applyChapterSelection(
  selection: ChapterExportSelection,
  volumes: VolumeWithChapters[],
  chapterIds: string[],
  shouldSelect: boolean,
  lastChapterAnchorId: string,
): ChapterExportSelection {
  const next = copySelection(selection);
  const chapterVolumeIds = new Map(
    volumes.flatMap((volume) => volume.chapters.map((chapter) => [chapter.id, volume.id] as const)),
  );

  for (const chapterId of chapterIds) {
    const volumeId = chapterVolumeIds.get(chapterId);
    if (!volumeId) continue;
    if (next.selectedVolumeIds.has(volumeId)) {
      if (shouldSelect) next.excludedChapterIds.delete(chapterId);
      else next.excludedChapterIds.add(chapterId);
      continue;
    }
    if (shouldSelect) next.includedChapterIds.add(chapterId);
    else next.includedChapterIds.delete(chapterId);
  }
  next.lastChapterAnchorId = lastChapterAnchorId;
  return next;
}

function copySelection(selection: ChapterExportSelection): ChapterExportSelection {
  return {
    selectedVolumeIds: new Set(selection.selectedVolumeIds),
    includedChapterIds: new Set(selection.includedChapterIds),
    excludedChapterIds: new Set(selection.excludedChapterIds),
    lastChapterAnchorId: selection.lastChapterAnchorId,
  };
}
