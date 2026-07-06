import { Badge, Box, Button, Dialog, Flex, ScrollArea, Text, TextField } from "@radix-ui/themes";
import { Bot, ChevronDown, Search, Terminal, User } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { countTokens } from "@/lib/tiktoken-utils";

import "./prompt-chain-dialog.css";

export interface PromptChainDialogEntry {
  role: string;
  content: string;
  name?: string;
}

interface PromptChainDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entries: PromptChainDialogEntry[];
  isLoading: boolean;
  title?: string;
  description?: string;
}

interface CountedPromptEntry extends PromptChainDialogEntry {
  tokenCount: number;
}

function getRoleMeta(
  role: string,
  t: ReturnType<typeof useTranslation>["t"],
): { label: string; Icon: typeof Terminal } {
  if (role === "system") return { label: t("promptChains.roleSystem"), Icon: Terminal };
  if (role === "assistant") return { label: t("promptChains.roleAssistant"), Icon: Bot };
  if (role === "user") return { label: t("promptChains.roleUser"), Icon: User };
  return { label: role || t("promptChainDialog.unknownRole"), Icon: Terminal };
}

function highlightContent(content: string, query: string): ReactNode {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) return content;

  const lowerContent = content.toLowerCase();
  const lowerQuery = trimmedQuery.toLowerCase();
  const parts: ReactNode[] = [];
  let cursor = 0;
  let matchIndex = lowerContent.indexOf(lowerQuery);

  while (matchIndex !== -1) {
    if (matchIndex > cursor) parts.push(content.slice(cursor, matchIndex));
    const end = matchIndex + trimmedQuery.length;
    parts.push(
      <mark
        className="prompt-chain-dialog-highlight"
        key={`${matchIndex}-${end}`}
      >
        {content.slice(matchIndex, end)}
      </mark>,
    );
    cursor = end;
    matchIndex = lowerContent.indexOf(lowerQuery, cursor);
  }

  if (cursor < content.length) parts.push(content.slice(cursor));
  return parts;
}

export function PromptChainDialog({
  open,
  onOpenChange,
  entries,
  isLoading,
  title,
  description,
}: PromptChainDialogProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedIndexes, setExpandedIndexes] = useState<Set<number>>(new Set());
  const [countedEntries, setCountedEntries] = useState<CountedPromptEntry[]>([]);

  useEffect(() => {
    if (!open || isLoading) return;

    const timer = window.setTimeout(() => {
      const nextEntries = entries.map((entry) => ({
        ...entry,
        tokenCount: countTokens(entry.content),
      }));
      setCountedEntries(nextEntries);
      setExpandedIndexes(new Set(nextEntries.map((_, index) => index)));
    }, 0);

    return () => window.clearTimeout(timer);
  }, [entries, isLoading, open]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setSearchQuery("");
      setExpandedIndexes(new Set());
      setCountedEntries([]);
    }
    onOpenChange(nextOpen);
  };

  const totalTokens = useMemo(
    () => countedEntries.reduce((total, entry) => total + entry.tokenCount, 0),
    [countedEntries],
  );

  const isBusy = isLoading || (open && !isLoading && countedEntries.length !== entries.length);

  const toggleEntry = (index: number) => {
    setExpandedIndexes((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const resolvedTitle = title ?? t("promptChainDialog.title");

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content className="prompt-chain-dialog-content">
        <Flex
          justify="between"
          align="start"
          gap="4"
          mb="3"
        >
          <Box>
            <Dialog.Title>{resolvedTitle}</Dialog.Title>
            <Dialog.Description
              size="2"
              color="gray"
            >
              {description ||
                (isBusy
                  ? t("promptChainDialog.loadingWithToken")
                  : t("promptChainDialog.summary", {
                      count: countedEntries.length,
                      tokens: totalTokens,
                    }))}
            </Dialog.Description>
          </Box>
          {!isBusy ? (
            <Badge
              color="gray"
              variant="soft"
            >
              {totalTokens} tokens
            </Badge>
          ) : null}
        </Flex>

        <TextField.Root
          className="prompt-chain-dialog-search"
          value={searchQuery}
          placeholder={t("promptChainDialog.searchPlaceholder")}
          disabled={isBusy}
          onChange={(event) => setSearchQuery(event.target.value)}
        >
          <TextField.Slot>
            <Search size={15} />
          </TextField.Slot>
        </TextField.Root>

        {isBusy ? (
          <Flex
            className="prompt-chain-dialog-loading"
            align="center"
            justify="center"
          >
            <Spinner size={18} />
            <Text
              color="gray"
              size="2"
            >
              {t("promptChainDialog.loading")}
            </Text>
          </Flex>
        ) : (
          <ScrollArea className="prompt-chain-dialog-scroll-area">
            <Flex
              className="prompt-chain-dialog-list"
              direction="column"
              gap="2"
            >
              {countedEntries.map((entry, index) => {
                const { label, Icon } = getRoleMeta(entry.role, t);
                const isExpanded = expandedIndexes.has(index);
                return (
                  <Box
                    className="prompt-chain-dialog-entry"
                    data-expanded={isExpanded}
                    key={`${entry.role}-${index}`}
                  >
                    <button
                      type="button"
                      className="prompt-chain-dialog-entry-header"
                      aria-expanded={isExpanded}
                      onClick={() => toggleEntry(index)}
                    >
                      <Flex
                        align="center"
                        gap="2"
                        className="prompt-chain-dialog-entry-title"
                      >
                        <Icon
                          size={14}
                          aria-hidden="true"
                        />
                        <Text
                          size="2"
                          weight="medium"
                        >
                          {entry.name || label}
                        </Text>
                        <Badge
                          color="gray"
                          variant="soft"
                        >
                          {label}
                        </Badge>
                      </Flex>
                      <Flex
                        align="center"
                        gap="2"
                      >
                        <Text
                          size="1"
                          color="gray"
                        >
                          {entry.tokenCount} tokens
                        </Text>
                        <span className="prompt-chain-dialog-toggle-icon">
                          <ChevronDown
                            size={14}
                            aria-hidden="true"
                          />
                        </span>
                      </Flex>
                    </button>
                    {isExpanded ? (
                      <Box className="prompt-chain-dialog-entry-content">
                        {entry.content ? (
                          highlightContent(entry.content, searchQuery)
                        ) : (
                          <Text color="gray">{t("promptChainDialog.emptyContent")}</Text>
                        )}
                      </Box>
                    ) : null}
                  </Box>
                );
              })}
            </Flex>
          </ScrollArea>
        )}

        <Flex
          mt="4"
          justify="end"
        >
          <Dialog.Close>
            <Button
              color="gray"
              variant="soft"
            >
              {t("common.close")}
            </Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
