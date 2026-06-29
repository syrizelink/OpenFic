/* eslint-disable react-refresh/only-export-components */
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Flex,
  IconButton,
  Popover,
  ScrollArea,
  Text,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import {
  AlertCircle,
  ChevronDown,
  Component,
  RefreshCw,
  Search,
} from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import type { ReactNode } from "react";

import type { AvailableModel, TaskType } from "@/lib/model.types";
import { Spinner } from "@/components";
import {
  CapabilityIcon,
  ContextBadge,
  getModelCapabilityKeys,
  formatContextWindow,
} from "./model-capability-tags";

const MotionBox = motion.create(Box);

export interface ModelIdSelectOption extends AvailableModel {
  value?: string;
}

interface ModelIdSelectProps {
  value: string;
  onChange: (value: string, name?: string) => void;
  models: ModelIdSelectOption[];
  isLoading?: boolean;
  placeholder?: string;
  disabled?: boolean;
  taskType?: TaskType;
  error?: string;
  editable?: boolean;
  allowCustomValue?: boolean;
  showRefreshButton?: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  refreshDisabled?: boolean;
  emptyOptionLabel?: string;
  compact?: boolean;
  triggerStyle?: React.CSSProperties;
  triggerPrefix?: ReactNode;
  hideTriggerChevron?: boolean;
  triggerClassName?: string;
}

export function getModelValue(model: ModelIdSelectOption): string {
  return model.value ?? model.id;
}

const PRICE_FORMATTER = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 4,
});

function formatPricePerMillion(value: number | null | undefined): string | null {
  if (!Number.isFinite(value) || value === null || value === undefined || value < 0) {
    return null;
  }

  return `$${PRICE_FORMATTER.format(value)} /M`;
}

function formatModelPriceLine(
  model: Pick<
    AvailableModel,
    "inputPricePerMillion" | "outputPricePerMillion" | "cacheReadPricePerMillion"
  >,
  labels: {
    input: string;
    output: string;
    cacheRead: string;
  }
): string | null {
  const inputPrice = formatPricePerMillion(model.inputPricePerMillion);
  const outputPrice = formatPricePerMillion(model.outputPricePerMillion);
  const cacheReadPrice = formatPricePerMillion(model.cacheReadPricePerMillion);
  const parts = [
    inputPrice ? `${inputPrice} ${labels.input}` : null,
    outputPrice ? `${outputPrice} ${labels.output}` : null,
    cacheReadPrice ? `${cacheReadPrice} ${labels.cacheRead}` : null,
  ].filter((part): part is string => Boolean(part));

  return parts.length > 0 ? parts.join(" · ") : null;
}

function ToolCallWarningBadge({ message }: { message: string }) {
  return (
    <Tooltip content={message}>
      <Box
        aria-label={message}
        role="img"
        style={{
          width: 18,
          height: 18,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 5,
          color: "#d44f4f",
          flexShrink: 0,
        }}
      >
        <AlertCircle size={12} strokeWidth={2.2} />
      </Box>
    </Tooltip>
  );
}

export function ModelIdSelect({
  value,
  onChange,
  models,
  isLoading = false,
  placeholder,
  disabled = false,
  taskType = "llm",
  error,
  editable = true,
  allowCustomValue = true,
  showRefreshButton = false,
  onRefresh,
  isRefreshing = false,
  refreshDisabled = false,
  emptyOptionLabel,
  compact = false,
  triggerStyle,
  triggerPrefix,
  hideTriggerChevron = false,
  triggerClassName,
}: ModelIdSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState(value || "");
  const [isListReady, setIsListReady] = useState(false);
  const listReadyFrameRef = useRef<number | null>(null);

  const popoverWidth = compact ? 360 : 500;
  const headerPad = compact ? "1" : "2";
  const itemPadding = compact ? "8px 12px" : "12px 16px";
  const modelNameSize = compact ? "1" : "2";
  const labelSize = compact ? "1" : "2";
  const showSearchBox = !compact || models.length >= 8;
  const scrollAreaHeight = compact ? "auto" : 300;
  const placeholderHeight = compact ? "auto" : 200;

  const selectedModel = useMemo(
    () => models.find((model) => getModelValue(model) === value),
    [models, value]
  );

  const filteredModels = useMemo(() => {
    if (!open || !isListReady) {
      return [];
    }
    if (!searchQuery.trim()) {
      return models;
    }

    const query = searchQuery.toLowerCase();
    return models.filter((model) => model.id.toLowerCase().includes(query));
  }, [isListReady, models, open, searchQuery]);

  useEffect(() => {
    if (!open || isLoading || isListReady) {
      return;
    }

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
  }, [isListReady, isLoading, open]);

  const showCustomOption =
    allowCustomValue && searchQuery.trim() && filteredModels.length === 0 && models.length > 0;

  const handleSelectModel = (model: ModelIdSelectOption) => {
    const nextValue = getModelValue(model);
    onChange(nextValue, model.name);
    setSearchQuery(model.id);
    setOpen(false);
  };

  const handleUseCustom = () => {
    onChange(searchQuery);
    setOpen(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!editable) {
      return;
    }

    const newValue = e.target.value;
    setSearchQuery(newValue);
    onChange(newValue);
  };

  const handleClearSelection = () => {
    onChange("");
    setSearchQuery("");
    setOpen(false);
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (disabled) {
      return;
    }

    if (listReadyFrameRef.current !== null) {
      cancelAnimationFrame(listReadyFrameRef.current);
      listReadyFrameRef.current = null;
    }

    if (newOpen) {
      setSearchQuery(editable ? value || "" : "");
      setIsListReady(false);
    } else {
      setSearchQuery(editable ? value || "" : "");
      setIsListReady(false);
    }

    setOpen(newOpen);
  };

  const triggerValue = editable
    ? open
      ? searchQuery
      : value || ""
    : selectedModel?.name ?? value;

  const trigger = editable ? (
    <Box style={{ position: "relative" }}>
      <TextField.Root
        value={triggerValue}
        onChange={handleInputChange}
        placeholder={placeholder || t("models.modelIdPlaceholder")}
        style={{ paddingRight: 32 }}
        disabled={disabled}
        readOnly={false}
      />
      <Box
        style={{
          position: "absolute",
          right: 8,
          top: "50%",
          transform: "translateY(-50%)",
          pointerEvents: "none",
        }}
      >
        <ChevronDown size={16} color="var(--gray-11)" />
      </Box>
    </Box>
  ) : (
    <Button
      type="button"
      variant="surface"
      color={compact ? undefined : "gray"}
      size={compact ? "1" : "2"}
      disabled={disabled}
      className={triggerClassName}
      style={{
        width: "100%",
        justifyContent: "space-between",
        ...triggerStyle,
      }}
    >
      <Flex align="center" gap="2" className="select-trigger-content">
        {triggerPrefix ?? (compact ? <Component size={14} aria-hidden="true" /> : null)}
        <Text color={selectedModel ? undefined : "gray"} truncate>
          {selectedModel?.name || placeholder || t("models.modelIdPlaceholder")}
        </Text>
      </Flex>
      {hideTriggerChevron ? null : <ChevronDown size={16} aria-hidden="true" />}
    </Button>
  );

  if (disabled) {
    return trigger;
  }

  return (
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
      <Popover.Trigger>{trigger}</Popover.Trigger>

      <Popover.Content
        style={{
          width: popoverWidth,
          minWidth: popoverWidth,
          padding: compact ? 4 : undefined,
        }}
        align="start"
      >
        <Box style={{ maxHeight: 400, overflow: "hidden" }}>
          {showSearchBox || showRefreshButton ? (
            <Box p={headerPad} style={{ borderBottom: "1px solid var(--gray-a4)" }}>
              <Flex align="center" gap={compact ? "1" : "2"}>
                {showSearchBox ? (
                  <TextField.Root
                    size={compact ? "1" : "2"}
                    placeholder={t("models.searchModel")}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    autoFocus
                    style={{ flex: 1 }}
                  >
                    <TextField.Slot>
                      <Search size={compact ? 14 : 16} />
                    </TextField.Slot>
                  </TextField.Root>
                ) : null}
                {showRefreshButton ? (
                  <IconButton
                    size="1"
                    variant="soft"
                    onClick={onRefresh}
                    disabled={refreshDisabled || !onRefresh || isRefreshing}
                    aria-label={t("models.fetchRemoteModels")}
                    title={t("models.fetchRemoteModels")}
                  >
                    {isRefreshing ? (
                      <Spinner size={18} />
                    ) : (
                      <RefreshCw size={14} />
                    )}
                  </IconButton>
                ) : null}
              </Flex>
            </Box>
          ) : null}

          <ScrollArea style={{ height: scrollAreaHeight }}>
            {isLoading || (open && !isListReady) ? (
              <Flex
                align="center"
                justify="center"
                direction="column"
                gap="2"
                style={{ height: placeholderHeight, padding: 20 }}
              >
                <Spinner size={18} />
                <Text size={labelSize} color="gray">
                  {t("models.loadingModels")}
                </Text>
              </Flex>
            ) : error ? (
              <Flex
                align="center"
                justify="center"
                direction="column"
                gap="2"
                style={{ height: placeholderHeight, padding: 20 }}
              >
                <Text size="2" color="red" align="center" weight="medium">
                  {t("models.loadModelsFailed")}
                </Text>
                <Text size="1" color="gray" align="center" style={{ maxWidth: 300 }}>
                  {error}
                </Text>
                {allowCustomValue ? (
                  <Text size="1" color="gray" align="center">
                    {t("models.manualInputHint")}
                  </Text>
                ) : null}
              </Flex>
            ) : models.length === 0 ? (
              <Flex direction="column">
                {emptyOptionLabel ? (
                  <MotionBox
                    onClick={handleClearSelection}
                    style={{
                      padding: itemPadding,
                      cursor: "pointer",
                      borderBottom: "1px solid var(--gray-a3)",
                    }}
                    whileHover={{ backgroundColor: "var(--gray-a2)" }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Text size={labelSize} color="gray">
                      {emptyOptionLabel}
                    </Text>
                  </MotionBox>
                ) : null}
                <Flex
                  align="center"
                  justify="center"
                  direction="column"
                  gap="2"
                  style={{ height: placeholderHeight, padding: 20 }}
                >
                  <Text size={labelSize} color="gray" align="center">
                    {t("models.noModelsAvailable")}
                  </Text>
                  {allowCustomValue ? (
                    <Text size="1" color="gray" align="center">
                      {t("models.manualInputHint")}
                    </Text>
                  ) : null}
                </Flex>
              </Flex>
            ) : (
              <Flex direction="column">
                {emptyOptionLabel ? (
                  <MotionBox
                    onClick={handleClearSelection}
                    style={{
                      padding: itemPadding,
                      cursor: "pointer",
                      borderBottom: "1px solid var(--gray-a3)",
                    }}
                    whileHover={{ backgroundColor: "var(--gray-a2)" }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Text size={labelSize} color="gray">
                      {emptyOptionLabel}
                    </Text>
                  </MotionBox>
                ) : null}

                {showCustomOption ? (
                  <MotionBox
                    onClick={handleUseCustom}
                    style={{
                      padding: itemPadding,
                      cursor: "pointer",
                      borderBottom: "1px solid var(--gray-a3)",
                      backgroundColor: "var(--blue-a2)",
                    }}
                    whileHover={{ backgroundColor: "var(--blue-a3)" }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Flex direction="column" gap="1">
                      <Text size="2" weight="medium" color="blue">
                        {t("models.useCustomModelId", {
                          modelId: searchQuery,
                        })}
                      </Text>
                      <Text size="1" color="gray">
                        {t("models.customModelIdHint")}
                      </Text>
                    </Flex>
                  </MotionBox>
                ) : null}

                {filteredModels.map((model) => {
                  const capabilityKeys = getModelCapabilityKeys(model);
                  const contextLabel = formatContextWindow(model.contextWindow);
                  const hasMetadata =
                    model.reasoning !== null &&
                    model.reasoning !== undefined
                      ? true
                      : model.toolCall !== null && model.toolCall !== undefined
                        ? true
                        : (model.inputModalities?.length ?? 0) > 0 ||
                          model.limit !== null ||
                          model.cost !== null ||
                          model.contextWindow !== null ||
                          model.inputPricePerMillion !== null ||
                          model.outputPricePerMillion !== null ||
                          model.cacheReadPricePerMillion !== null;
                  const showToolCallWarning =
                    taskType === "llm" && hasMetadata && model.toolCall === false;
                  const priceLine = formatModelPriceLine(model, {
                    input: t("models.priceInputLabel"),
                    output: t("models.priceOutputLabel"),
                    cacheRead: t("models.priceCacheReadLabel"),
                  });

                  return (
                    <MotionBox
                      key={getModelValue(model)}
                      onClick={() => handleSelectModel(model)}
                      style={{
                        padding: itemPadding,
                        cursor: "pointer",
                        borderBottom: "1px solid var(--gray-a3)",
                      }}
                      whileHover={{ backgroundColor: "var(--gray-a2)" }}
                      whileTap={{ scale: 0.98 }}
                      transition={{ duration: 0.15 }}
                    >
                      <Flex direction="column" gap="1">
                        <Flex align="start" justify="between" gap="2">
                          <Flex align="center" gap="1" style={{ minWidth: 0 }}>
                            <Text
                              size={modelNameSize}
                              weight="medium"
                              style={{
                                minWidth: 0,
                                color: showToolCallWarning ? "#c64545" : undefined,
                              }}
                            >
                              {model.name}
                            </Text>
                            {showToolCallWarning ? (
                              <ToolCallWarningBadge
                                message={t("models.toolCallWarningTooltip")}
                              />
                            ) : null}
                          </Flex>
                          {capabilityKeys.length > 0 || contextLabel ? (
                            <Flex
                              align="center"
                              gap="1"
                              wrap="wrap"
                              justify="end"
                              style={{ marginLeft: "auto", flexShrink: 0 }}
                            >
                              {capabilityKeys.map((capability) => (
                                <CapabilityIcon
                                  key={`${getModelValue(model)}-${capability}`}
                                  capability={capability}
                                />
                              ))}
                              {contextLabel ? <ContextBadge label={contextLabel} /> : null}
                            </Flex>
                          ) : null}
                        </Flex>
                        {compact ? null : (
                          <Text size="1" color="gray">
                            {priceLine || model.id}
                          </Text>
                        )}
                      </Flex>
                    </MotionBox>
                  );
                })}

                {filteredModels.length === 0 && !showCustomOption ? (
                  <Flex
                    align="center"
                    justify="center"
                    style={{ height: placeholderHeight, padding: 20 }}
                  >
                    <Text size={labelSize} color="gray">
                      {t("projects.noProjectsFound")}
                    </Text>
                  </Flex>
                ) : null}
              </Flex>
            )}
          </ScrollArea>
        </Box>
      </Popover.Content>
    </Popover.Root>
  );
}
