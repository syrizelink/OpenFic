interface SummaryRangeEndpoint {
  volumeTitle: string | null;
  chapterOrder: number;
  chapterTitle: string;
}

export function formatSummaryRangeMeta({
  volumeTitle,
  chapterOrder,
}: Omit<SummaryRangeEndpoint, "chapterTitle">): string {
  return volumeTitle ? `${volumeTitle} | ${chapterOrder}` : `${chapterOrder}.`;
}

function formatSummaryRangeEndpoint({
  volumeTitle,
  chapterOrder,
  chapterTitle,
}: SummaryRangeEndpoint): string {
  const chapter = `${chapterOrder} ${chapterTitle}`.trim();
  return volumeTitle ? `${volumeTitle} | ${chapter}` : chapter;
}

export function formatSummaryRangeTitle({
  startVolumeTitle,
  startOrder,
  startChapterTitle,
  endVolumeTitle,
  endOrder,
  endChapterTitle,
}: {
  startVolumeTitle: string | null;
  startOrder: number;
  startChapterTitle: string;
  endVolumeTitle: string | null;
  endOrder: number;
  endChapterTitle: string;
}): string {
  return `${formatSummaryRangeEndpoint({ volumeTitle: startVolumeTitle, chapterOrder: startOrder, chapterTitle: startChapterTitle })} - ${formatSummaryRangeEndpoint({ volumeTitle: endVolumeTitle, chapterOrder: endOrder, chapterTitle: endChapterTitle })}`;
}
