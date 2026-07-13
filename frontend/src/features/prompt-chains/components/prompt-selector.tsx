import { Box, Flex, Popover, ScrollArea, Text, TextField } from "@radix-ui/themes";
import { Check, ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";

import type { PromptCategoryMetadata, PromptMetadata } from "@/lib/prompt-chain.types";

import "./prompt-selector.css";

interface PromptSelectorProps {
  categories: PromptCategoryMetadata[];
  value: string | null;
  onChange: (promptId: string) => void;
}

function getPromptLabel(prompt: PromptMetadata, t: (key: string) => string): string {
  return prompt.label ?? t(`promptChains.prompts.${prompt.label_key}`);
}

export function PromptSelector({ categories, value, onChange }: PromptSelectorProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearchQuery = useDeferredValue(searchQuery.trim().toLocaleLowerCase());
  const selectedPrompt = categories
    .flatMap((category) => category.prompts)
    .find((prompt) => prompt.id === value);
  const visibleCategories = categories
    .map((category) => ({
      ...category,
      prompts: category.prompts.filter((prompt) => {
        if (!deferredSearchQuery) return true;
        const label = getPromptLabel(prompt, t).toLocaleLowerCase();
        return label.includes(deferredSearchQuery) || prompt.id.includes(deferredSearchQuery);
      }),
    }))
    .filter((category) => category.prompts.length > 0);

  function handleOpenChange(nextOpen: boolean) {
    setIsOpen(nextOpen);
    if (!nextOpen) setSearchQuery("");
  }

  function handleSelect(promptId: string) {
    onChange(promptId);
    setIsOpen(false);
    setSearchQuery("");
  }

  return (
    <Popover.Root
      open={isOpen}
      onOpenChange={handleOpenChange}
    >
      <Popover.Trigger>
        <button
          type="button"
          className="prompt-selector-trigger"
          aria-label={t("promptChains.selectPrompt")}
        >
          <Text
            size="1"
            color="gray"
            className="prompt-selector-prefix"
          >
            {t("promptChains.promptTemplate")}
          </Text>
          <Text
            size="2"
            truncate
          >
            {selectedPrompt
              ? getPromptLabel(selectedPrompt, t)
              : t("promptChains.promptPlaceholder")}
          </Text>
          <ChevronDown
            size={16}
            aria-hidden="true"
          />
        </button>
      </Popover.Trigger>

      <Popover.Content
        align="start"
        className="prompt-selector-content"
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <Box className="prompt-selector-search">
          <TextField.Root
            size="2"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={t("select.searchPlaceholder")}
          >
            <TextField.Slot>
              <Search
                size={16}
                aria-hidden="true"
              />
            </TextField.Slot>
          </TextField.Root>
        </Box>

        <ScrollArea className="prompt-selector-list">
          {visibleCategories.length > 0 ? (
            <Flex direction="column">
              {visibleCategories.map((category) => (
                <Box
                  key={category.id}
                  className="prompt-selector-category"
                >
                  <Text
                    size="1"
                    weight="medium"
                    color="gray"
                    className="prompt-selector-category-label"
                  >
                    {t(`promptChains.categories.${category.label_key}`)}
                  </Text>
                  {category.prompts.map((prompt) => {
                    const isSelected = prompt.id === value;
                    return (
                      <button
                        key={prompt.id}
                        type="button"
                        data-state={isSelected ? "checked" : "unchecked"}
                        className="prompt-selector-option"
                        onClick={() => handleSelect(prompt.id)}
                      >
                        <Text
                          size="2"
                          truncate
                        >
                          {getPromptLabel(prompt, t)}
                        </Text>
                        {isSelected ? (
                          <Check
                            size={15}
                            aria-label={t("promptChains.selectedPrompt")}
                          />
                        ) : null}
                      </button>
                    );
                  })}
                </Box>
              ))}
            </Flex>
          ) : (
            <Text
              size="2"
              color="gray"
              align="center"
              className="prompt-selector-empty"
            >
              {t("select.noMatchingOptions")}
            </Text>
          )}
        </ScrollArea>
      </Popover.Content>
    </Popover.Root>
  );
}
