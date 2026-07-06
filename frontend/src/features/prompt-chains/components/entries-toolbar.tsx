/**
 * Entries Toolbar Component
 *
 * 条目列表工具栏，包含搜索框和新建按钮
 */

import { Box, Flex, TextField, IconButton, Tooltip } from "@radix-ui/themes";
import { Search, Plus, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { PromptEntryData } from "@/lib/prompt-chain.types";

import { EntrySearch } from "./entry-search";

interface EntriesToolbarProps {
  entries: PromptEntryData[];
  onEntrySelect: (entryId: string) => void;
  onCreateEntry: () => void;
}

export function EntriesToolbar({ entries, onEntrySelect, onCreateEntry }: EntriesToolbarProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (value.trim()) {
      setSearchOpen(true);
    }
  };

  const handleSelect = (entryId: string) => {
    onEntrySelect(entryId);
    setQuery("");
    setSearchOpen(false);
  };

  return (
    <Box
      style={{
        padding: "12px",
        borderBottom: "1px solid var(--gray-a5)",
        background: "var(--color-background)",
      }}
    >
      <Flex
        gap="2"
        align="center"
      >
        {/* 搜索框 */}
        <EntrySearch
          query={query}
          entries={entries}
          onSelect={handleSelect}
          open={searchOpen}
          onOpenChange={setSearchOpen}
        >
          <Box style={{ flex: 1, minWidth: 0 }}>
            <TextField.Root
              size="2"
              placeholder={t("promptChains.searchEntriesPlaceholder")}
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              onFocus={() => {
                if (query.trim()) {
                  setSearchOpen(true);
                }
              }}
              onClick={(e) => {
                e.stopPropagation();
                if (query.trim()) {
                  setSearchOpen(true);
                }
              }}
              style={{ width: "100%" }}
            >
              <TextField.Slot>
                <Search size={14} />
              </TextField.Slot>
              {query && (
                <TextField.Slot>
                  <IconButton
                    variant="ghost"
                    size="1"
                    onClick={() => {
                      setQuery("");
                      setSearchOpen(false);
                    }}
                  >
                    <X size={12} />
                  </IconButton>
                </TextField.Slot>
              )}
            </TextField.Root>
          </Box>
        </EntrySearch>

        {/* 新建按钮 */}
        <Tooltip content={t("promptChains.newEntry")}>
          <IconButton
            variant="ghost"
            size="2"
            aria-label={t("promptChains.newEntry")}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              onCreateEntry();
            }}
          >
            <Plus size={16} />
          </IconButton>
        </Tooltip>
      </Flex>
    </Box>
  );
}
