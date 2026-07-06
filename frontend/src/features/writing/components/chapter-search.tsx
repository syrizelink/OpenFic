import { Box, Text, TextField, DropdownMenu, IconButton } from "@radix-ui/themes";
import Fuse from "fuse.js";
import { Search, X } from "lucide-react";
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Virtuoso } from "react-virtuoso";

import type { ChapterListItem, VolumeWithChapters } from "@/lib/chapter.types";
import { getPinyin, getInitials } from "@/lib/pinyin-search";

interface ChapterSearchProps {
  volumes: VolumeWithChapters[];
  onChapterSelect: (chapterId: string) => void;
  isDisabled?: boolean;
  onDisabledClick?: () => void;
}

interface SearchableChapter {
  id: string;
  title: string;
  volumeTitle: string;
  titlePinyin: string;
  titleInitials: string;
  volumeTitlePinyin: string;
  volumeTitleInitials: string;
  wordCount: number;
}

interface SearchResult {
  chapter: SearchableChapter;
  originalChapter: ChapterListItem;
  titleMatches: Array<[number, number]>;
}

function HighlightedText({ text, matches }: { text: string; matches: Array<[number, number]> }) {
  if (matches.length === 0) return <>{text}</>;

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  const sortedMatches = [...matches].sort((a, b) => a[0] - b[0]);
  const mergedMatches: Array<[number, number]> = [];

  for (const match of sortedMatches) {
    if (mergedMatches.length === 0) {
      mergedMatches.push([...match]);
      continue;
    }

    const last = mergedMatches[mergedMatches.length - 1];
    if (match[0] <= last[1] + 1) {
      last[1] = Math.max(last[1], match[1]);
    } else {
      mergedMatches.push([...match]);
    }
  }

  for (const [start, end] of mergedMatches) {
    if (start > lastIndex) {
      parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex, start)}</span>);
    }

    parts.push(
      <mark
        key={`match-${start}`}
        style={{
          background: "var(--accent-a4)",
          color: "inherit",
          padding: "0 2px",
          borderRadius: "2px",
        }}
      >
        {text.slice(start, end + 1)}
      </mark>,
    );
    lastIndex = end + 1;
  }

  if (lastIndex < text.length) {
    parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex)}</span>);
  }

  return <>{parts}</>;
}

export function ChapterSearch({
  volumes,
  onChapterSelect,
  isDisabled = false,
  onDisabledClick,
}: ChapterSearchProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const searchableChapters = useMemo((): SearchableChapter[] => {
    return volumes.flatMap((volume) =>
      volume.chapters.map((chapter) => ({
        id: chapter.id,
        title: chapter.title,
        volumeTitle: volume.title,
        titlePinyin: getPinyin(chapter.title),
        titleInitials: getInitials(chapter.title),
        volumeTitlePinyin: getPinyin(volume.title),
        volumeTitleInitials: getInitials(volume.title),
        wordCount: chapter.wordCount,
      })),
    );
  }, [volumes]);

  const chapterMap = useMemo(() => {
    const map = new Map<string, ChapterListItem>();
    volumes.forEach((volume) => {
      volume.chapters.forEach((chapter) => map.set(chapter.id, chapter));
    });
    return map;
  }, [volumes]);

  const fuse = useMemo(() => {
    return new Fuse(searchableChapters, {
      keys: [
        { name: "title", weight: 3 },
        { name: "titlePinyin", weight: 2 },
        { name: "titleInitials", weight: 2.5 },
        { name: "volumeTitle", weight: 1 },
        { name: "volumeTitlePinyin", weight: 0.8 },
        { name: "volumeTitleInitials", weight: 1 },
      ],
      includeMatches: true,
      threshold: 0.1,
      ignoreLocation: true,
      distance: 50,
      useExtendedSearch: false,
    });
  }, [searchableChapters]);

  const searchResults = useMemo((): SearchResult[] => {
    if (!query.trim()) return [];

    const results = fuse.search(query, { limit: 20 });
    return results.map((result) => {
      const titleMatches: Array<[number, number]> = [];

      result.matches?.forEach((match) => {
        const indices = match.indices as Array<[number, number]>;
        if (match.key === "title") titleMatches.push(...indices);
      });

      return {
        chapter: result.item,
        originalChapter: chapterMap.get(result.item.id)!,
        titleMatches,
      };
    });
  }, [chapterMap, fuse, query]);

  const handleTriggerClick = () => {
    if (!isDisabled) return;
    onDisabledClick?.();
    setOpen(false);
  };

  const handleSelect = (chapterId: string) => {
    onChapterSelect(chapterId);
    setQuery("");
    setOpen(false);
  };

  return (
    <DropdownMenu.Root
      open={isDisabled ? false : open}
      onOpenChange={setOpen}
    >
      <DropdownMenu.Trigger>
        <IconButton
          variant="ghost"
          size="2"
          onClick={handleTriggerClick}
        >
          <Search size={16} />
        </IconButton>
      </DropdownMenu.Trigger>

      <DropdownMenu.Content
        align="start"
        style={{ width: 320, maxWidth: 320, minWidth: 320 }}
      >
        <Box p="2">
          <TextField.Root
            size="2"
            placeholder={t("writing.searchPlaceholder")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            autoFocus
          >
            <TextField.Slot>
              <Search size={14} />
            </TextField.Slot>
            {query && (
              <TextField.Slot>
                <IconButton
                  variant="ghost"
                  size="1"
                  onClick={() => setQuery("")}
                >
                  <X size={12} />
                </IconButton>
              </TextField.Slot>
            )}
          </TextField.Root>
        </Box>

        <DropdownMenu.Separator />

        <Box style={{ maxHeight: 350, overflowY: "auto", overflowX: "hidden" }}>
          {query.trim() && (
            <>
              {searchResults.length === 0 ? (
                <Box p="4">
                  <Text
                    size="2"
                    color="gray"
                    align="center"
                  >
                    {t("writing.noChaptersFound")}
                  </Text>
                </Box>
              ) : (
                <Virtuoso
                  style={{ height: 300 }}
                  data={searchResults}
                  itemContent={(index, result) => (
                    <Box
                      onClick={() => handleSelect(result.chapter.id)}
                      style={{
                        padding: "12px 16px",
                        cursor: "pointer",
                        borderBottom:
                          index < searchResults.length - 1 ? "1px solid var(--gray-a4)" : "none",
                        background: "transparent",
                        transition: "background 0.1s ease",
                      }}
                      onMouseEnter={(event) => {
                        event.currentTarget.style.background = "var(--gray-a3)";
                      }}
                      onMouseLeave={(event) => {
                        event.currentTarget.style.background = "transparent";
                      }}
                    >
                      <Text
                        size="2"
                        weight="medium"
                        style={{
                          display: "block",
                          marginBottom: "4px",
                          lineHeight: 1.5,
                          color: "var(--gray-12)",
                        }}
                      >
                        <span>{result.chapter.volumeTitle || t("volume.untitled")} / </span>
                        <HighlightedText
                          text={result.chapter.title || t("writing.untitledChapter")}
                          matches={result.titleMatches}
                        />
                      </Text>
                      <Text
                        size="1"
                        color="gray"
                      >
                        {result.originalChapter.wordCount} {t("writing.words")}
                      </Text>
                    </Box>
                  )}
                />
              )}
            </>
          )}
        </Box>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}
