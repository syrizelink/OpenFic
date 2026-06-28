import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { ContentSearchPopover } from "@/components/content-search-popover";
import type { ContentSearchResultItem } from "@/components/content-search-popover";
import { searchChapters } from "@/lib/api-client";
import type { ChapterSearchResultItem } from "@/lib/api-client";

interface ChapterSearchPopoverProps {
  projectId: string;
  query: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigateToChapter: (chapterId: string) => void;
  children: React.ReactNode;
}

function toSearchResultItem(item: ChapterSearchResultItem): ContentSearchResultItem {
  return {
    id: item.chapterId,
    title: item.chapterTitle,
    subtitle: item.volumeTitle,
    matches: item.matches.map((m) => ({
      lineNumber: m.lineNumber,
      lineText: m.lineText,
    })),
  };
}

export function ChapterSearchPopover({
  projectId,
  query,
  open,
  onOpenChange,
  onNavigateToChapter,
  children,
}: ChapterSearchPopoverProps) {
  const { t } = useTranslation();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedQuery, setDebouncedQuery] = useState("");

  const prevOpenRef = useRef(open);

  useEffect(() => {
    if (open && !prevOpenRef.current && query.trim()) {
      setDebouncedQuery(query);
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    }
    prevOpenRef.current = open;
  }, [open, query]);

  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, open]);

  const { data, isLoading } = useQuery({
    queryKey: ["chapters-search", projectId, debouncedQuery],
    queryFn: () => searchChapters(projectId, debouncedQuery),
    enabled: !!projectId && debouncedQuery.trim().length > 0 && open,
    staleTime: 0,
  });

  const results: ContentSearchResultItem[] = (data?.results ?? []).map(toSearchResultItem);

  const handleNavigate = useCallback(
    (itemId: string, _lineNumber: number) => {
      onNavigateToChapter(itemId);
    },
    [onNavigateToChapter]
  );

  return (
    <ContentSearchPopover
      query={debouncedQuery}
      open={open}
      onOpenChange={onOpenChange}
      results={results}
      totalItems={data?.totalChapters ?? 0}
      totalMatches={data?.totalMatches ?? 0}
      isLoading={isLoading}
      onNavigateToMatch={handleNavigate}
      emptyPlaceholder={t("writing.searchPlaceholder")}
      searchingText={t("writing.searching")}
      noResultsText={t("writing.noChaptersFound")}
      resultSummaryText={t("writing.searchResultSummary")}
      expandAllText={t("writing.expandAll")}
      collapseAllText={t("writing.collapseAll")}
    >
      {children}
    </ContentSearchPopover>
  );
}
