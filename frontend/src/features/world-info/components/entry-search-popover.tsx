import { useCallback, useEffect, useRef, useState } from "react";
import { Box, Flex, IconButton, Popover, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ChevronsUpDown } from "lucide-react";

import { searchWorldInfoEntries } from "@/lib/api-client";
import type {
  WorldInfoEntrySearchResult,
} from "@/lib/world-info.types";

interface EntrySearchPopoverProps {
  worldInfoId: string;
  query: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigateToMatch: (entryId: string, lineNumber: number) => void;
  children: React.ReactNode;
}

function highlightText(text: string, query: string): React.ReactNode {
  if (!query) return text;

  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  let idx = lowerText.indexOf(lowerQuery, lastIndex);
  while (idx !== -1) {
    if (idx > lastIndex) {
      parts.push(
        <span key={`t-${lastIndex}`}>{text.slice(lastIndex, idx)}</span>
      );
    }
    parts.push(
      <mark
        key={`m-${idx}`}
        style={{
          background: "var(--accent-a4)",
          color: "inherit",
          padding: "0 2px",
          borderRadius: "2px",
        }}
      >
        {text.slice(idx, idx + query.length)}
      </mark>
    );
    lastIndex = idx + query.length;
    idx = lowerText.indexOf(lowerQuery, lastIndex);
  }

  if (lastIndex < text.length) {
    parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex)}</span>);
  }

  return <>{parts}</>;
}

function EntryResultGroup({
  result,
  query,
  collapsed,
  onToggle,
  onNavigateToMatch,
}: {
  result: WorldInfoEntrySearchResult;
  query: string;
  collapsed: boolean;
  onToggle: () => void;
  onNavigateToMatch: (entryId: string, lineNumber: number) => void;
}) {
  const ChevronIcon = collapsed ? ChevronRight : ChevronDown;

  return (
    <Box>
      <Flex
        align="center"
        gap="1"
        onClick={onToggle}
        style={{
          padding: "6px 12px",
          cursor: "pointer",
          userSelect: "none",
          transition: "background 0.1s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "var(--gray-a3)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
      >
        <ChevronIcon size={14} style={{ color: "var(--gray-a9)", flexShrink: 0 }} />
        <Text
          size="2"
          weight="bold"
          style={{
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {result.entryName}
        </Text>
        <Box
          style={{
            minWidth: 20,
            height: 18,
            borderRadius: 999,
            background: "var(--blue-a4)",
            color: "var(--blue-11)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "0 5px",
            flexShrink: 0,
          }}
        >
          <Text size="1" style={{ lineHeight: 1 }}>
            {result.matches.length}
          </Text>
        </Box>
      </Flex>

      {!collapsed && (
        <Box
          style={{
            position: "relative",
            marginLeft: 19,
            paddingLeft: 8,
          }}
        >
          <Box
            style={{
              position: "absolute",
              left: 0,
              top: 4,
              bottom: 4,
              width: 1,
              background: "var(--gray-a5)",
            }}
          />
          {result.matches.map((match) => (
            <Box
              key={`${result.entryId}-${match.lineNumber}`}
              onClick={() => onNavigateToMatch(result.entryId, match.lineNumber)}
              style={{
                paddingTop: 2,
                paddingBottom: 2,
                paddingRight: 12,
                cursor: "pointer",
                transition: "background 0.1s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--gray-a3)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <Text
                size="1"
                style={{
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  display: "block",
                }}
              >
                {highlightText(match.lineText, query)}
              </Text>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

export function EntrySearchPopover({
  worldInfoId,
  query,
  open,
  onOpenChange,
  onNavigateToMatch,
  children,
}: EntrySearchPopoverProps) {
  const { t } = useTranslation();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [allCollapsed, setAllCollapsed] = useState(false);

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
      setCollapsedIds(new Set());
      setAllCollapsed(false);
    }, 300);
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, open]);

  const { data, isLoading } = useQuery({
    queryKey: ["world-info-entries-search", worldInfoId, debouncedQuery],
    queryFn: () => searchWorldInfoEntries(worldInfoId, debouncedQuery),
    enabled: !!worldInfoId && debouncedQuery.trim().length > 0 && open,
    staleTime: 0,
  });

  const hasResults = data && data.results.length > 0;

  const handleToggleEntry = useCallback((entryId: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(entryId)) {
        next.delete(entryId);
      } else {
        next.add(entryId);
      }
      return next;
    });
  }, []);

  const handleToggleAll = useCallback(() => {
    if (!data) return;
    setAllCollapsed((prev) => {
      const next = !prev;
      if (next) {
        setCollapsedIds(new Set(data.results.map((r) => r.entryId)));
      } else {
        setCollapsedIds(new Set());
      }
      return next;
    });
  }, [data]);

  const handleNavigate = useCallback(
    (entryId: string, lineNumber: number) => {
      onNavigateToMatch(entryId, lineNumber);
      onOpenChange(false);
    },
    [onNavigateToMatch, onOpenChange]
  );

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger
        style={{
          border: "none",
          background: "transparent",
          padding: 0,
          width: "100%",
        }}
      >
        {children}
      </Popover.Trigger>

      <Popover.Content
        align="start"
        side="bottom"
        sideOffset={4}
        onOpenAutoFocus={(e) => e.preventDefault()}
        style={{ width: 360, maxWidth: 360, padding: 0 }}
      >
        <Box
          style={{
            maxHeight: 400,
            overflowY: "auto",
            overflowX: "hidden",
          }}
        >
          {debouncedQuery.trim().length === 0 ? (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {t("worldInfo.searchPlaceholder")}
              </Text>
            </Box>
          ) : isLoading ? (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {t("worldInfo.searching")}
              </Text>
            </Box>
          ) : hasResults ? (
            <>
              <Flex
                align="center"
                justify="between"
                style={{
                  padding: "8px 12px",
                  borderBottom: "1px solid var(--gray-a5)",
                  background: "var(--gray-a2)",
                }}
              >
                <Text size="1" color="gray">
                  {t("worldInfo.searchResultSummary", {
                    entries: data.totalEntries,
                    matches: data.totalMatches,
                  })}
                </Text>
                <IconButton
                  variant="ghost"
                  size="1"
                  onClick={handleToggleAll}
                  title={
                    allCollapsed
                      ? t("worldInfo.expandAll")
                      : t("worldInfo.collapseAll")
                  }
                >
                  <ChevronsUpDown size={14} />
                </IconButton>
              </Flex>
              {data.results.map((result) => (
                <EntryResultGroup
                  key={result.entryId}
                  result={result}
                  query={debouncedQuery}
                  collapsed={collapsedIds.has(result.entryId)}
                  onToggle={() => handleToggleEntry(result.entryId)}
                  onNavigateToMatch={handleNavigate}
                />
              ))}
            </>
          ) : (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {t("worldInfo.noEntriesFound")}
              </Text>
            </Box>
          )}
        </Box>
      </Popover.Content>
    </Popover.Root>
  );
}
