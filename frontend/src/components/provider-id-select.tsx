import { Box, Flex, Popover, ScrollArea, Text, TextField } from "@radix-ui/themes";
import { ChevronDown, Component, Search } from "lucide-react";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ProviderIcon } from "@/features/settings/lib/provider-icons";
import type { ModelProviderCatalogProvider } from "@/lib/model.types";

import { Spinner } from "./spinner";

import "./provider-id-select.css";

export interface ProviderIdSelectProps {
  value: string;
  onChange: (value: string) => void;
  providers: ModelProviderCatalogProvider[];
  placeholder: string;
  disabled?: boolean;
}

interface ProviderIdSelectOption {
  value: string;
  label: string;
  iconPath: string | null;
}

const OPENAI_COMPATIBLE_OPTION: ProviderIdSelectOption = {
  value: "openai-compatible",
  label: "OpenAI Compatible",
  iconPath: null,
};

export function ProviderIdSelect({
  value,
  onChange,
  providers,
  placeholder,
  disabled = false,
}: ProviderIdSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isListReady, setIsListReady] = useState(false);
  const listReadyFrameRef = useRef<number | null>(null);
  const options = useMemo<ProviderIdSelectOption[]>(() => {
    const catalogOptions = providers.map((provider) => ({
      value: provider.providerType,
      label: provider.displayName,
      iconPath: provider.iconPath,
    }));

    if (!catalogOptions.some((option) => option.value === OPENAI_COMPATIBLE_OPTION.value)) {
      catalogOptions.push(OPENAI_COMPATIBLE_OPTION);
    }

    return catalogOptions.sort((left, right) => left.label.localeCompare(right.label));
  }, [providers]);
  const selectedOption = options.find((option) => option.value === value);
  const filteredOptions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return options;

    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(query) || option.value.toLowerCase().includes(query),
    );
  }, [options, searchQuery]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (listReadyFrameRef.current !== null) {
      cancelAnimationFrame(listReadyFrameRef.current);
      listReadyFrameRef.current = null;
    }

    setOpen(nextOpen);
    setIsListReady(false);
    if (!nextOpen) setSearchQuery("");
  };

  const handleSelect = (nextValue: string) => {
    onChange(nextValue);
    setOpen(false);
    setSearchQuery("");
  };

  useEffect(() => {
    if (!open || isListReady) return;

    listReadyFrameRef.current = requestAnimationFrame(() => {
      startTransition(() => {
        setIsListReady(true);
        listReadyFrameRef.current = null;
      });
    });

    return () => {
      if (listReadyFrameRef.current !== null) {
        cancelAnimationFrame(listReadyFrameRef.current);
        listReadyFrameRef.current = null;
      }
    };
  }, [isListReady, open]);

  const trigger = (
    <Box
      className="provider-id-select-trigger"
      data-disabled={disabled ? "true" : "false"}
    >
      <TextField.Root
        size="2"
        value={selectedOption?.label ?? ""}
        placeholder={placeholder}
        readOnly
        disabled={disabled}
        data-slot="provider-id-select-trigger"
        data-state={open ? "open" : "closed"}
      >
        {selectedOption ? (
          <TextField.Slot>
            <ProviderOptionIcon
              option={selectedOption}
              size={16}
            />
          </TextField.Slot>
        ) : null}
        <TextField.Slot side="right">
          <ChevronDown
            size={16}
            aria-hidden="true"
          />
        </TextField.Slot>
      </TextField.Root>
    </Box>
  );

  if (disabled) return trigger;

  return (
    <Popover.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Popover.Trigger>{trigger}</Popover.Trigger>

      <Popover.Content
        align="start"
        data-slot="provider-id-select-content"
        className="provider-id-select-content"
      >
        <Box
          p="1"
          className="provider-id-select-search"
        >
          <TextField.Root
            size="2"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={t("select.searchPlaceholder")}
            autoFocus
          >
            <TextField.Slot>
              <Search
                size={18}
                aria-hidden="true"
              />
            </TextField.Slot>
          </TextField.Root>
        </Box>

        <ScrollArea
          scrollbars="vertical"
          className="provider-id-select-list"
        >
          {!isListReady ? (
            <Flex
              align="center"
              justify="center"
              className="provider-id-select-loading"
            >
              <Spinner size={18} />
            </Flex>
          ) : (
            <Flex direction="column">
              {filteredOptions.length > 0 ? (
                filteredOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    data-slot="provider-id-select-item"
                    data-state={option.value === value ? "checked" : "unchecked"}
                    className="provider-id-select-item"
                    onClick={() => handleSelect(option.value)}
                  >
                    <Flex
                      align="center"
                      gap="2"
                    >
                      <ProviderOptionIcon
                        option={option}
                        size={18}
                      />
                      <Text
                        size="2"
                        truncate
                      >
                        {option.label}
                      </Text>
                    </Flex>
                  </button>
                ))
              ) : (
                <Text
                  size="2"
                  color="gray"
                  align="center"
                  className="provider-id-select-empty"
                >
                  {t("select.noMatchingOptions")}
                </Text>
              )}
            </Flex>
          )}
        </ScrollArea>
      </Popover.Content>
    </Popover.Root>
  );
}

function ProviderOptionIcon({ option, size }: { option?: ProviderIdSelectOption; size: number }) {
  if (option?.iconPath) {
    return (
      <ProviderIcon
        iconPath={option.iconPath}
        size={size}
      />
    );
  }

  return (
    <Component
      size={size}
      aria-hidden="true"
      className="provider-id-select-fallback-icon"
    />
  );
}
