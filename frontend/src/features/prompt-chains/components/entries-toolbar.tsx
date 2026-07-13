/**
 * Entries Toolbar Component
 *
 * 条目列表工具栏，包含搜索和操作按钮。
 */

import { Box, Flex, IconButton, Tooltip } from "@radix-ui/themes";
import { Play, Plus, Save, Search } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import "./entries-toolbar.css";

import { EntrySearch } from "./entry-search";

interface EntriesToolbarProps {
  promptId: string;
  versionId: string;
  onEntrySelect: (entryId: string) => void;
  onCreateEntry: () => void;
  onCompile: () => void;
  canCompile: boolean;
  onSave: () => void;
  canSave: boolean;
}

export function EntriesToolbar({
  promptId,
  versionId,
  onEntrySelect,
  onCreateEntry,
  onCompile,
  canCompile,
  onSave,
  canSave,
}: EntriesToolbarProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchExpanded, setSearchExpanded] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!searchExpanded || !searchContainerRef.current) return;
    searchContainerRef.current.querySelector("input")?.focus();
  }, [searchExpanded]);

  const handleSearchChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
    if (event.target.value.trim()) setSearchOpen(true);
  }, []);

  const handleSearchToggle = useCallback(() => {
    setSearchExpanded((previous) => {
      if (previous) {
        setSearchOpen(false);
        return false;
      }
      return true;
    });
    if (!searchExpanded && query.trim()) setSearchOpen(true);
  }, [query, searchExpanded]);

  const handleSearchBlur = useCallback(() => {
    if (!query.trim()) setSearchExpanded(false);
  }, [query]);

  const handlePopoverOpenChange = useCallback((open: boolean) => {
    setSearchOpen(open);
    if (!open) setSearchExpanded(false);
  }, []);

  const handleSelect = useCallback(
    (entryId: string) => {
      onEntrySelect(entryId);
      setQuery("");
      setSearchOpen(false);
      setSearchExpanded(false);
    },
    [onEntrySelect],
  );

  return (
    <Box className="prompt-chain-entries-toolbar">
      <Flex
        gap="1"
        align="center"
        className="prompt-chain-entries-toolbar-row"
      >
        <div
          ref={searchContainerRef}
          className="prompt-chain-entries-search"
          data-expanded={searchExpanded}
        >
          <EntrySearch
            promptId={promptId}
            versionId={versionId}
            query={query}
            open={searchOpen}
            onOpenChange={handlePopoverOpenChange}
            onNavigateToMatch={handleSelect}
          >
            <div className="prompt-chain-entries-search-popover-anchor" />
          </EntrySearch>
          <IconButton
            variant="ghost"
            size="2"
            aria-label={t("promptChains.searchEntries")}
            onClick={searchExpanded ? undefined : handleSearchToggle}
            className="prompt-chain-entries-search-button"
            data-expanded={searchExpanded}
          >
            <Search size={16} />
          </IconButton>
          <motion.div
            animate={{ width: searchExpanded ? 200 : 0, opacity: searchExpanded ? 1 : 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="prompt-chain-entries-search-input-wrap"
          >
            <input
              type="text"
              value={query}
              placeholder={t("promptChains.searchEntriesPlaceholder")}
              onChange={handleSearchChange}
              onFocus={() => {
                if (query.trim()) setSearchOpen(true);
              }}
              onBlur={handleSearchBlur}
              className="prompt-chain-entries-search-input"
            />
          </motion.div>
        </div>

        {!searchExpanded && (
          <>
            <Box className="prompt-chain-entries-toolbar-spacer" />
            <Tooltip content={t("promptChains.newEntry")}>
              <IconButton
                variant="ghost"
                size="2"
                aria-label={t("promptChains.newEntry")}
                onPointerDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  onCreateEntry();
                }}
              >
                <Plus size={16} />
              </IconButton>
            </Tooltip>

            <Tooltip
              content={
                canCompile ? t("promptChains.compile") : t("promptChains.compileRequiresSave")
              }
            >
              <IconButton
                variant="ghost"
                size="2"
                aria-label={t("promptChains.compile")}
                onClick={onCompile}
                disabled={!canCompile}
              >
                <Play size={16} />
              </IconButton>
            </Tooltip>

            <Tooltip content={t("promptChains.save")}>
              <IconButton
                variant="ghost"
                size="2"
                aria-label={t("promptChains.save")}
                onClick={onSave}
                disabled={!canSave}
              >
                <Save size={16} />
              </IconButton>
            </Tooltip>
          </>
        )}
      </Flex>
    </Box>
  );
}
