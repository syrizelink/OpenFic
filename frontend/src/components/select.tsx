/**
 * Labeled Select Component
 *
 * 通用的带标签的下拉选择组件，封装了 Radix UI Select 组件。
 * 提供一致的样式和用户体验。
 */

import { Box, Button, Flex, Popover, ScrollArea, Select, Text, TextField } from "@radix-ui/themes";
import { ChevronDown, Search } from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import type { CSSProperties, ReactNode, ComponentProps } from "react";
import { useTranslation } from "react-i18next";

import "./select.css";

type TextColor = ComponentProps<typeof Text>["color"];

export interface SelectOption {
  value: string;
  label: string;
  prefix?: ReactNode;
  suffix?: ReactNode;
  description?: string;
  labelColor?: string;
  fontFamily?: string;
  disabled?: boolean;
  separatorAfter?: boolean;
}

function SelectOptionContent({ option, size }: { option: SelectOption; size: "1" | "2" | "3" }) {
  const main = option.description ? (
    <Flex
      direction="column"
      align="start"
      gap="0"
      justify="center"
      className="select-option-main select-option-main--stacked"
    >
      <Flex
        align="center"
        gap="2"
        className="select-option-main__title"
      >
        {option.prefix}
        <Text
          size={size}
          truncate
          style={{
            fontFamily: option.fontFamily,
            ...(option.labelColor ? { color: option.labelColor } : undefined),
          }}
        >
          {option.label}
        </Text>
      </Flex>
      <Text
        size="1"
        color="gray"
        className="select-option-description"
      >
        {option.description}
      </Text>
    </Flex>
  ) : (
    <Flex
      align="center"
      gap="2"
      className="select-option-main"
    >
      {option.prefix}
      <Text
        size={size}
        truncate
        style={{
          fontFamily: option.fontFamily,
          ...(option.labelColor ? { color: option.labelColor } : undefined),
        }}
      >
        {option.label}
      </Text>
    </Flex>
  );

  return (
    <Flex
      align="center"
      gap="2"
      justify="between"
      className="select-option-row"
    >
      {main}
      {option.suffix}
    </Flex>
  );
}

export interface LabeledSelectProps {
  label?: string;
  value: string | undefined;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  size?: "1" | "2" | "3";
  triggerStyle?: CSSProperties;
  contentPosition?: "item-aligned" | "popper";
  labelSize?: "1" | "2" | "3";
  labelWeight?: "regular" | "medium" | "bold";
  labelColor?: TextColor;
  layout?: "vertical" | "horizontal";
  gap?: "1" | "2" | "3" | "4" | "5";
  triggerLabelVisible?: boolean;
  triggerPrefix?: ReactNode;
  hideTriggerChevron?: boolean;
  triggerClassName?: string;
  contentClassName?: string;
}

export interface SearchableSelectProps extends LabeledSelectProps {
  searchPlaceholder?: string;
  emptyMessage?: string;
  contentHeight?: CSSProperties["height"];
}

export function LabeledSelect({
  label,
  value,
  options,
  onChange,
  placeholder,
  disabled = false,
  size = "2",
  triggerStyle,
  contentPosition = "popper",
  labelSize = "2",
  labelWeight = "medium",
  labelColor,
  layout = "vertical",
  gap = "2",
  triggerLabelVisible = true,
  triggerPrefix,
  triggerClassName,
  contentClassName,
}: LabeledSelectProps) {
  const selectedOption = options.find((opt) => opt.value === value);
  const triggerLabel = selectedOption?.label || placeholder;

  const selectControl = (
    <Select.Root
      value={value || undefined}
      onValueChange={onChange}
      disabled={disabled}
      size={size}
    >
      <Select.Trigger
        className={triggerClassName}
        style={
          selectedOption?.labelColor
            ? ({
                "--select-label-color": selectedOption.labelColor,
                ...triggerStyle,
              } as CSSProperties)
            : triggerStyle
        }
        placeholder={placeholder}
      >
        <Flex
          align="center"
          justify={triggerLabelVisible ? undefined : "center"}
          gap={triggerLabelVisible ? "2" : "0"}
          className={triggerLabelVisible ? undefined : "select-trigger-content--icon-only"}
        >
          {triggerPrefix}
          {selectedOption?.prefix}
          {triggerLabelVisible && triggerLabel && (
            <Text
              size={size}
              color={selectedOption ? undefined : "gray"}
              className="select-option-label"
              style={{ fontFamily: selectedOption?.fontFamily }}
            >
              {triggerLabel}
            </Text>
          )}
        </Flex>
      </Select.Trigger>
      <Select.Content
        position={contentPosition}
        className={contentClassName}
      >
        {options.map((option) => (
          <Fragment key={option.value}>
            <Select.Item
              value={option.value}
              disabled={option.disabled}
            >
              <SelectOptionContent
                option={option}
                size={size}
              />
            </Select.Item>
            {option.separatorAfter ? <Select.Separator /> : null}
          </Fragment>
        ))}
      </Select.Content>
    </Select.Root>
  );

  if (!label) {
    return selectControl;
  }

  if (layout === "horizontal") {
    return (
      <Flex
        align="center"
        gap={gap}
      >
        <Text
          size={labelSize}
          weight={labelWeight}
          color={labelColor}
        >
          {label}
        </Text>
        {selectControl}
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      gap={gap}
    >
      <Text
        size={labelSize}
        weight={labelWeight}
        color={labelColor}
      >
        {label}
      </Text>
      {selectControl}
    </Flex>
  );
}

export function SimpleSelect({
  value,
  options,
  onChange,
  placeholder,
  disabled = false,
  size = "2",
  triggerStyle,
  contentPosition = "popper",
  triggerPrefix,
  triggerClassName,
  contentClassName,
}: Omit<
  LabeledSelectProps,
  "label" | "labelSize" | "labelWeight" | "labelColor" | "layout" | "gap"
>) {
  const selectedOption = options.find((opt) => opt.value === value);
  const triggerLabel = selectedOption?.label || placeholder;

  return (
    <Select.Root
      value={value || undefined}
      onValueChange={onChange}
      disabled={disabled}
      size={size}
    >
      <Select.Trigger
        className={triggerClassName}
        style={
          selectedOption?.labelColor
            ? ({
                "--select-label-color": selectedOption.labelColor,
                ...triggerStyle,
              } as CSSProperties)
            : triggerStyle
        }
        placeholder={placeholder}
      >
        <Flex
          align="center"
          gap="2"
          className="select-trigger-content"
        >
          {triggerPrefix}
          {selectedOption?.prefix}
          {triggerLabel && (
            <Text
              size={size}
              color={selectedOption ? undefined : "gray"}
              className="select-option-label"
              style={{ fontFamily: selectedOption?.fontFamily }}
            >
              {triggerLabel}
            </Text>
          )}
        </Flex>
      </Select.Trigger>
      <Select.Content
        position={contentPosition}
        className={contentClassName}
      >
        {options.map((option) => (
          <Fragment key={option.value}>
            <Select.Item
              value={option.value}
              disabled={option.disabled}
            >
              <SelectOptionContent
                option={option}
                size={size}
              />
            </Select.Item>
            {option.separatorAfter ? <Select.Separator /> : null}
          </Fragment>
        ))}
      </Select.Content>
    </Select.Root>
  );
}

export function SearchableSelect({
  label,
  value,
  options,
  onChange,
  placeholder,
  disabled = false,
  size = "2",
  triggerStyle,
  labelSize = "2",
  labelWeight = "medium",
  labelColor,
  layout = "vertical",
  gap = "2",
  searchPlaceholder,
  emptyMessage,
  contentHeight = 260,
}: SearchableSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const resolvedSearchPlaceholder = searchPlaceholder ?? t("select.searchPlaceholder");
  const resolvedEmptyMessage = emptyMessage ?? t("select.noMatchingOptions");
  const selectedOption = options.find((opt) => opt.value === value);

  const filteredOptions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return options;

    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(query) || option.value.toLowerCase().includes(query),
    );
  }, [options, searchQuery]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) setSearchQuery("");
    setOpen(nextOpen);
  };

  const handleSelect = (nextValue: string) => {
    onChange(nextValue);
    setOpen(false);
    setSearchQuery("");
  };

  const selectControl = (
    <Popover.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Popover.Trigger>
        <Button
          type="button"
          variant="surface"
          color="gray"
          disabled={disabled}
          data-slot="searchable-select-trigger"
          data-state={open ? "open" : "closed"}
          style={{ width: "100%", justifyContent: "space-between", ...triggerStyle }}
          size={size}
        >
          <Flex
            align="center"
            gap="2"
            className="select-trigger-content"
          >
            {selectedOption?.prefix}
            <Text
              size={size}
              color={selectedOption ? undefined : "gray"}
              className="select-option-label"
              style={{ fontFamily: selectedOption?.fontFamily }}
            >
              {selectedOption?.label || placeholder}
            </Text>
          </Flex>
          <ChevronDown
            size={16}
            aria-hidden="true"
          />
        </Button>
      </Popover.Trigger>

      <Popover.Content
        align="start"
        data-slot="searchable-select-content"
        className="searchable-select-content"
        style={{ width: "var(--radix-popover-trigger-width)" }}
      >
        <Box
          p="2"
          className="searchable-select-search-box"
        >
          <TextField.Root
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={resolvedSearchPlaceholder}
            autoFocus
            size={size}
          >
            <TextField.Slot>
              <Search
                size={16}
                aria-hidden="true"
              />
            </TextField.Slot>
          </TextField.Root>
        </Box>

        <ScrollArea style={{ height: contentHeight }}>
          <Flex
            direction="column"
            py="1"
          >
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  disabled={option.disabled}
                  data-slot="searchable-select-item"
                  data-state={option.value === value ? "checked" : "unchecked"}
                  className="searchable-select-item"
                  onClick={() => handleSelect(option.value)}
                >
                  <SelectOptionContent
                    option={option}
                    size={size}
                  />
                </button>
              ))
            ) : (
              <Flex
                align="center"
                justify="center"
                p="4"
              >
                <Text
                  size="2"
                  color="gray"
                >
                  {resolvedEmptyMessage}
                </Text>
              </Flex>
            )}
          </Flex>
        </ScrollArea>
      </Popover.Content>
    </Popover.Root>
  );

  if (!label) {
    return selectControl;
  }

  if (layout === "horizontal") {
    return (
      <Flex
        align="center"
        gap={gap}
      >
        <Text
          size={labelSize}
          weight={labelWeight}
          color={labelColor}
        >
          {label}
        </Text>
        {selectControl}
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      gap={gap}
    >
      <Text
        size={labelSize}
        weight={labelWeight}
        color={labelColor}
      >
        {label}
      </Text>
      {selectControl}
    </Flex>
  );
}
