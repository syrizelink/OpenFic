import type { VolumeWithChapters } from "@/lib/chapter.types";

export interface GroupedVolumeListScrollRequest {
  key: string;
  type: "chapter" | "volume";
  chapterId?: string;
  volumeId?: string;
}

export type GroupedVolumeListScrollTarget =
  | {
      type: "expand-volume";
      volumeId: string;
    }
  | {
      type: "chapter";
      index: number;
      align: "center" | "end";
      behavior: "smooth";
    }
  | {
      type: "group";
      groupIndex: number;
      align: "end";
      behavior: "smooth";
    };

interface ResolveCurrentChapterNavigationParams {
  volumes: VolumeWithChapters[];
  expandedVolumeIds: Set<string>;
  currentChapterId: string | null;
  getChapterScrollIndex: (chapterId: string) => number | undefined;
}

interface ResolveInitialCurrentChapterNavigationParams extends ResolveCurrentChapterNavigationParams {
  initialNavigationKey: string | null;
}

interface GetInitialCurrentChapterVolumeIdToExpandParams {
  initialNavigationKey: string | null;
  volumes: VolumeWithChapters[];
  expandedVolumeIds: Set<string>;
  currentChapterId: string | null;
}

interface ResolveGroupedVolumeListScrollRequestParams {
  request: GroupedVolumeListScrollRequest | null;
  volumes: VolumeWithChapters[];
  getChapterScrollIndex: (chapterId: string) => number | undefined;
}

export function findVolumeIdForChapter(
  volumes: VolumeWithChapters[],
  chapterId: string | null
): string | null {
  if (!chapterId) {
    return null;
  }

  for (const volume of volumes) {
    if (volume.chapters.some((chapter) => chapter.id === chapterId)) {
      return volume.id;
    }
  }

  return null;
}

export function resolveCurrentChapterNavigation({
  volumes,
  expandedVolumeIds,
  currentChapterId,
  getChapterScrollIndex,
}: ResolveCurrentChapterNavigationParams): GroupedVolumeListScrollTarget | null {
  const volumeId = findVolumeIdForChapter(volumes, currentChapterId);
  if (!currentChapterId || !volumeId) {
    return null;
  }

  if (!expandedVolumeIds.has(volumeId)) {
    return {
      type: "expand-volume",
      volumeId,
    };
  }

  const index = getChapterScrollIndex(currentChapterId);
  if (typeof index !== "number") {
    return null;
  }

  return {
    type: "chapter",
    index,
    align: "center",
    behavior: "smooth",
  };
}

export function getInitialCurrentChapterVolumeIdToExpand({
  initialNavigationKey,
  volumes,
  expandedVolumeIds,
  currentChapterId,
}: GetInitialCurrentChapterVolumeIdToExpandParams): string | null {
  if (!initialNavigationKey) {
    return null;
  }

  const volumeId = findVolumeIdForChapter(volumes, currentChapterId);
  if (!currentChapterId || !volumeId || expandedVolumeIds.has(volumeId)) {
    return null;
  }

  return volumeId;
}

export function resolveInitialCurrentChapterNavigation({
  initialNavigationKey,
  ...params
}: ResolveInitialCurrentChapterNavigationParams): GroupedVolumeListScrollTarget | null {
  if (!initialNavigationKey) {
    return null;
  }

  return resolveCurrentChapterNavigation(params);
}

export function resolveGroupedVolumeListScrollRequest({
  request,
  volumes,
  getChapterScrollIndex,
}: ResolveGroupedVolumeListScrollRequestParams): GroupedVolumeListScrollTarget | null {
  if (!request) {
    return null;
  }

  if (request.type === "chapter") {
    if (!request.chapterId) {
      return null;
    }

    const index = getChapterScrollIndex(request.chapterId);
    if (typeof index !== "number") {
      return null;
    }

    return {
      type: "chapter",
      index,
      align: "end",
      behavior: "smooth",
    };
  }

  if (!request.volumeId) {
    return null;
  }

  const groupIndex = volumes.findIndex((volume) => volume.id === request.volumeId);
  if (groupIndex < 0) {
    return null;
  }

  return {
    type: "group",
    groupIndex,
    align: "end",
    behavior: "smooth",
  };
}
