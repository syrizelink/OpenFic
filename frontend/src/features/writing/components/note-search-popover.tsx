import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { ContentSearchPopover } from "@/components/content-search-popover";
import type { ContentSearchResultItem } from "@/components/content-search-popover";
import { searchNotes } from "@/lib/api-client";
import type { NoteSearchResultItem } from "@/lib/api-client";

interface NoteSearchPopoverProps {
  projectId: string;
  query: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigateToNote: (noteId: string) => void;
  children: React.ReactNode;
}

function toSearchResultItem(item: NoteSearchResultItem): ContentSearchResultItem {
  return {
    id: item.noteId,
    title: item.noteTitle,
    subtitle: item.categoryPath || undefined,
    matches: item.matches.map((m) => ({
      lineNumber: m.lineNumber,
      lineText: m.lineText,
    })),
  };
}

export function NoteSearchPopover({
  projectId,
  query,
  open,
  onOpenChange,
  onNavigateToNote,
  children,
}: NoteSearchPopoverProps) {
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
    queryKey: ["notes-search", projectId, debouncedQuery],
    queryFn: () => searchNotes(projectId, debouncedQuery),
    enabled: !!projectId && debouncedQuery.trim().length > 0 && open,
    staleTime: 0,
  });

  const results: ContentSearchResultItem[] = (data?.results ?? []).map(toSearchResultItem);

  const handleNavigate = useCallback(
    (itemId: string, _lineNumber: number) => {
      onNavigateToNote(itemId);
    },
    [onNavigateToNote]
  );

  return (
    <ContentSearchPopover
      query={debouncedQuery}
      open={open}
      onOpenChange={onOpenChange}
      results={results}
      totalItems={data?.totalNotes ?? 0}
      totalMatches={data?.totalMatches ?? 0}
      isLoading={isLoading}
      onNavigateToMatch={handleNavigate}
      emptyPlaceholder={t("writing.searchPlaceholder")}
      searchingText={t("writing.searching")}
      noResultsText={t("writing.noNotesFound")}
      resultSummaryText={t("writing.searchResultSummary")}
      expandAllText={t("writing.expandAll")}
      collapseAllText={t("writing.collapseAll")}
    >
      {children}
    </ContentSearchPopover>
  );
}
