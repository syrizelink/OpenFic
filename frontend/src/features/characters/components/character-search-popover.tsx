import { useCallback, useEffect, useRef, useState } from "react";
import { Box, Flex, IconButton, Popover, Text } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ChevronsUpDown } from "lucide-react";
import { useTranslation } from "react-i18next";

import { searchCharacters } from "@/lib/api-client";
import type { CharacterSearchResult } from "@/lib/character.types";

interface CharacterSearchPopoverProps {
  projectId: string;
  query: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigateToMatch: (characterId: string) => void;
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
      parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex, idx)}</span>);
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

  if (lastIndex < text.length) parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex)}</span>);

  return <>{parts}</>;
}

function CharacterResultGroup({
  result,
  query,
  collapsed,
  onToggle,
  onNavigateToMatch,
}: {
  result: CharacterSearchResult;
  query: string;
  collapsed: boolean;
  onToggle: () => void;
  onNavigateToMatch: (characterId: string) => void;
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
        onMouseEnter={(event) => {
          event.currentTarget.style.background = "var(--gray-a3)";
        }}
        onMouseLeave={(event) => {
          event.currentTarget.style.background = "transparent";
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
          {result.characterName}
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
          <Text size="1" style={{ lineHeight: 1 }}>{result.matches.length}</Text>
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
              key={`${result.characterId}-${match.lineNumber}-${match.lineText}`}
              onClick={() => onNavigateToMatch(result.characterId)}
              style={{
                paddingTop: 2,
                paddingBottom: 2,
                paddingRight: 12,
                cursor: "pointer",
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

export function CharacterSearchPopover({
  projectId,
  query,
  open,
  onOpenChange,
  onNavigateToMatch,
  children,
}: CharacterSearchPopoverProps) {
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
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query);
      setCollapsedIds(new Set());
      setAllCollapsed(false);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [open, query]);

  const { data, isLoading } = useQuery({
    queryKey: ["characters-search", projectId, debouncedQuery],
    queryFn: () => searchCharacters(projectId, debouncedQuery),
    enabled: !!projectId && debouncedQuery.trim().length > 0 && open,
    staleTime: 0,
  });

  const handleToggleCharacter = useCallback((characterId: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(characterId)) next.delete(characterId);
      else next.add(characterId);
      return next;
    });
  }, []);

  const handleToggleAll = useCallback(() => {
    if (!data) return;
    setAllCollapsed((prev) => {
      const next = !prev;
      setCollapsedIds(next ? new Set(data.results.map((result) => result.characterId)) : new Set());
      return next;
    });
  }, [data]);

  const handleNavigate = useCallback(
    (characterId: string) => {
      onNavigateToMatch(characterId);
      onOpenChange(false);
    },
    [onNavigateToMatch, onOpenChange]
  );

  const hasResults = data && data.results.length > 0;

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
        onOpenAutoFocus={(event) => event.preventDefault()}
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
            <Box p="4"><Text size="2" color="gray" align="center">{t("characters.searchPlaceholder")}</Text></Box>
          ) : isLoading ? (
            <Box p="4"><Text size="2" color="gray" align="center">{t("characters.searching")}</Text></Box>
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
                  {t("characters.searchResultSummary", {
                    characters: data.totalCharacters,
                    matches: data.totalMatches,
                  })}
                </Text>
                <IconButton variant="ghost" size="1" onClick={handleToggleAll} title={allCollapsed ? t("characters.expandAll") : t("characters.collapseAll")}>
                  <ChevronsUpDown size={14} />
                </IconButton>
              </Flex>
              {data.results.map((result) => (
                <CharacterResultGroup
                  key={result.characterId}
                  result={result}
                  query={debouncedQuery}
                  collapsed={collapsedIds.has(result.characterId)}
                  onToggle={() => handleToggleCharacter(result.characterId)}
                  onNavigateToMatch={handleNavigate}
                />
              ))}
            </>
          ) : (
            <Box p="4"><Text size="2" color="gray" align="center">{t("characters.noCharactersFound")}</Text></Box>
          )}
        </Box>
      </Popover.Content>
    </Popover.Root>
  );
}
