import { useCallback, useState } from "react";
import { Box, Flex, IconButton, Popover, Text } from "@radix-ui/themes";
import { ChevronDown, ChevronRight, ChevronsUpDown } from "lucide-react";

export interface ContentSearchMatch {
  lineNumber: number;
  lineText: string;
}

export interface ContentSearchResultItem {
  id: string;
  title: string;
  subtitle?: string;
  matches: ContentSearchMatch[];
}

interface ContentSearchPopoverProps {
  query: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  results: ContentSearchResultItem[];
  totalItems: number;
  totalMatches: number;
  isLoading: boolean;
  onNavigateToMatch: (itemId: string, lineNumber: number) => void;
  children: React.ReactNode;
  emptyPlaceholder: string;
  searchingText: string;
  noResultsText: string;
  resultSummaryText: string;
  expandAllText: string;
  collapseAllText: string;
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

function ResultGroup({
  item,
  query,
  collapsed,
  onToggle,
  onNavigateToMatch,
}: {
  item: ContentSearchResultItem;
  query: string;
  collapsed: boolean;
  onToggle: () => void;
  onNavigateToMatch: (itemId: string, lineNumber: number) => void;
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
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Flex align="baseline" gap="1" style={{ minWidth: 0 }}>
            <Text
              size="2"
              weight="bold"
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {item.title}
            </Text>
            {item.subtitle && (
              <Text
                size="1"
                style={{
                  color: "var(--gray-a9)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flexShrink: 1,
                }}
              >
                {item.subtitle}
              </Text>
            )}
          </Flex>
        </Box>
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
            {item.matches.length}
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
          {item.matches.map((match) => (
            <Box
              key={`${item.id}-${match.lineNumber}`}
              onClick={() => onNavigateToMatch(item.id, match.lineNumber)}
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

export function ContentSearchPopover({
  query,
  open,
  onOpenChange,
  results,
  totalItems,
  totalMatches,
  isLoading,
  onNavigateToMatch,
  children,
  emptyPlaceholder,
  searchingText,
  noResultsText,
  resultSummaryText,
  expandAllText,
  collapseAllText,
}: ContentSearchPopoverProps) {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [allCollapsed, setAllCollapsed] = useState(false);

  const hasResults = results.length > 0;

  const handleToggleItem = useCallback((itemId: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }, []);

  const handleToggleAll = useCallback(() => {
    setAllCollapsed((prev) => {
      const next = !prev;
      if (next) {
        setCollapsedIds(new Set(results.map((r) => r.id)));
      } else {
        setCollapsedIds(new Set());
      }
      return next;
    });
  }, [results]);

  const handleNavigate = useCallback(
    (itemId: string, lineNumber: number) => {
      onNavigateToMatch(itemId, lineNumber);
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
          {query.trim().length === 0 ? (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {emptyPlaceholder}
              </Text>
            </Box>
          ) : isLoading ? (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {searchingText}
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
                  {resultSummaryText
                    .replace("{items}", String(totalItems))
                    .replace("{matches}", String(totalMatches))}
                </Text>
                <IconButton
                  variant="ghost"
                  size="1"
                  onClick={handleToggleAll}
                  title={allCollapsed ? expandAllText : collapseAllText}
                >
                  <ChevronsUpDown size={14} />
                </IconButton>
              </Flex>
              {results.map((item) => (
                <ResultGroup
                  key={item.id}
                  item={item}
                  query={query}
                  collapsed={collapsedIds.has(item.id)}
                  onToggle={() => handleToggleItem(item.id)}
                  onNavigateToMatch={handleNavigate}
                />
              ))}
            </>
          ) : (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {noResultsText}
              </Text>
            </Box>
          )}
        </Box>
      </Popover.Content>
    </Popover.Root>
  );
}
