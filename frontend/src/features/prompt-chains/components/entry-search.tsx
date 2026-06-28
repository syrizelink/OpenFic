/**
 * Entry Search Component
 *
 * 条目搜索面板，支持拼音搜索
 */

import { useMemo } from "react";
import { Box, Text, Popover, Flex } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { Terminal, Bot, User } from "lucide-react";
import Fuse from "fuse.js";

import type { PromptEntryData } from "@/lib/prompt-chain.types";
import { getPinyin, getInitials } from "@/lib/pinyin-search";

interface EntrySearchProps {
  query: string;
  entries: PromptEntryData[];
  onSelect: (entryId: string) => void;
  children: React.ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface SearchableEntry {
  id: string;
  name: string;
  namePinyin: string;
  nameInitials: string;
  role: string;
}

interface SearchResult {
  entry: SearchableEntry;
  originalEntry: PromptEntryData;
  nameMatches: Array<[number, number]>;
}

/**
 * 高亮渲染文本
 */
function HighlightedText({
  text,
  matches,
}: {
  text: string;
  matches: Array<[number, number]>;
}) {
  if (matches.length === 0) {
    return <>{text}</>;
  }

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  // 按起始位置排序并合并重叠区间
  const sortedMatches = [...matches].sort((a, b) => a[0] - b[0]);
  const mergedMatches: Array<[number, number]> = [];

  for (const match of sortedMatches) {
    if (mergedMatches.length === 0) {
      mergedMatches.push([...match]);
    } else {
      const last = mergedMatches[mergedMatches.length - 1];
      if (match[0] <= last[1] + 1) {
        last[1] = Math.max(last[1], match[1]);
      } else {
        mergedMatches.push([...match]);
      }
    }
  }

  for (const [start, end] of mergedMatches) {
    // 添加非高亮部分
    if (start > lastIndex) {
      parts.push(
        <span key={`text-${lastIndex}`}>{text.slice(lastIndex, start)}</span>
      );
    }
    // 添加高亮部分
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
      </mark>
    );
    lastIndex = end + 1;
  }

  // 添加剩余部分
  if (lastIndex < text.length) {
    parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex)}</span>);
  }

  return <>{parts}</>;
}

export function EntrySearch({
  query,
  entries,
  onSelect,
  children,
  open,
  onOpenChange,
}: EntrySearchProps) {
  const { t } = useTranslation();
  // 预处理条目数据，生成拼音索引
  const searchableEntries = useMemo((): SearchableEntry[] => {
    return entries.map((e) => ({
      id: e.id || "",
      name: e.name,
      namePinyin: getPinyin(e.name),
      nameInitials: getInitials(e.name),
      role: e.role,
    }));
  }, [entries]);

  // 创建条目 ID 到原始条目的映射
  const entryMap = useMemo(() => {
    const map = new Map<string, PromptEntryData>();
    entries.forEach((e) => {
      if (e.id) map.set(e.id, e);
    });
    return map;
  }, [entries]);

  // 创建 Fuse 实例，支持拼音搜索
  const fuse = useMemo(() => {
    return new Fuse(searchableEntries, {
      keys: [
        { name: "name", weight: 3 },
        { name: "namePinyin", weight: 2 },
        { name: "nameInitials", weight: 2.5 },
      ],
      includeMatches: true,
      threshold: 0.3,
      ignoreLocation: true,
      distance: 50,
      useExtendedSearch: false,
    });
  }, [searchableEntries]);

  // 搜索结果
  const searchResults = useMemo((): SearchResult[] => {
    if (!query.trim() || query.trim().length < 1) return [];

    const results = fuse.search(query, { limit: 20 });

    return results.map((result) => {
      const nameMatches: Array<[number, number]> = [];

      result.matches?.forEach((match) => {
        const indices = match.indices as Array<[number, number]>;
        if (match.key === "name") {
          nameMatches.push(...indices);
        }
      });

      return {
        entry: result.item,
        originalEntry: entryMap.get(result.item.id)!,
        nameMatches,
      };
    });
  }, [fuse, query, entryMap]);

  const handleSelect = (entryId: string) => {
    onSelect(entryId);
    onOpenChange(false);
  };

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger style={{ border: "none", background: "transparent", padding: 0, width: "100%" }}>
        {children}
      </Popover.Trigger>

      <Popover.Content
        align="start"
        side="bottom"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onInteractOutside={(e) => {
          const target = e.target as HTMLElement;
          const inputElement = target.closest('input, [role="textbox"], [data-radix-popover-trigger]');
          if (inputElement) {
            e.preventDefault();
          }
        }}
        onPointerDownOutside={(e) => {
          const target = e.target as HTMLElement;
          const inputElement = target.closest('input, [role="textbox"], [data-radix-popover-trigger]');
          if (inputElement) {
            e.preventDefault();
          }
        }}
        style={{ width: 320, maxWidth: 280, minWidth: 280, padding: 0 }}
      >
        {/* 搜索结果 */}
        <Box 
          style={{ 
            maxHeight: 350, 
            overflowY: "auto", 
            overflowX: "hidden"
          }}
        >
          {query.trim() ? (
            <>
              {searchResults.length === 0 ? (
                <Box p="4">
                  <Text size="2" color="gray" align="center">
                    {t("promptChains.noEntriesFound")}
                  </Text>
                </Box>
              ) : (
                <Box>
                  {searchResults.map((result, index) => {
                    const originalEntry = result.originalEntry;
                    const RoleIcon =
                      result.entry.role === "system"
                        ? Terminal
                        : result.entry.role === "assistant"
                        ? Bot
                        : User;

                    return (
                      <Box
                        key={result.entry.id}
                        onClick={() => handleSelect(result.entry.id)}
                        style={{
                          padding: "12px 16px",
                          cursor: "pointer",
                          borderBottom:
                            index < searchResults.length - 1
                              ? "1px solid var(--gray-a4)"
                              : "none",
                          background: "transparent",
                          transition: "background 0.1s ease",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "var(--gray-a3)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "transparent";
                        }}
                      >
                        <Flex align="center" justify="between" gap="2">
                          {/* 左侧：角色图标 + 条目名称 */}
                          <Flex align="center" gap="2" style={{ flex: 1, minWidth: 0 }}>
                            {/* 角色图标 */}
                            <Box style={{ color: "var(--gray-a10)", flexShrink: 0 }}>
                              <RoleIcon size={14} />
                            </Box>

                            {/* 条目名称 */}
                            <Box style={{ flex: 1, minWidth: 0 }}>
                              <Text
                                size="2"
                                weight="medium"
                                style={{
                                  wordBreak: "break-word",
                                  lineHeight: 1.4,
                                }}
                              >
                                <HighlightedText
                                  text={result.entry.name || t("promptChains.untitledEntry")}
                                  matches={result.nameMatches}
                                />
                              </Text>
                            </Box>
                          </Flex>

                          {/* 右侧：状态点 + token数 */}
                          <Flex align="center" gap="0" style={{ flexShrink: 0 }}>
                            {/* 状态点（启用=绿点，未启用=红点） */}
                            <Box
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                background: originalEntry.is_enabled
                                  ? "var(--green-9)"
                                  : "var(--red-9)",
                                flexShrink: 0,
                              }}
                            />

                            {/* Token数 */}
                            <Text size="1" color="gray" style={{ minWidth: "32px", textAlign: "right" }}>
                              {originalEntry.token_count}
                            </Text>
                          </Flex>
                        </Flex>
                      </Box>
                    );
                  })}
                </Box>
              )}
            </>
          ) : (
            <Box p="4">
              <Text size="2" color="gray" align="center">
                {t("promptChains.searchPlaceholder")}
              </Text>
            </Box>
          )}
        </Box>
      </Popover.Content>
    </Popover.Root>
  );
}
