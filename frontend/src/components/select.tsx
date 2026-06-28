/**
 * Labeled Select Component
 *
 * 通用的带标签的下拉选择组件，封装了 Radix UI Select 组件。
 * 提供一致的样式和用户体验。
 */

import { Box, Button, Flex, Popover, ScrollArea, Select, Text, TextField } from "@radix-ui/themes";
import { ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode, ComponentProps } from "react";
import "./select.css";

type TextColor = ComponentProps<typeof Text>["color"];

export interface SelectOption {
  value: string;
  label: string;
  prefix?: ReactNode;
  suffix?: ReactNode;
  disabled?: boolean;
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
  layout = "vertical",
  gap = "2",
  triggerLabelVisible = true,
  triggerPrefix,
  triggerClassName,
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
      <Select.Trigger className={triggerClassName} style={triggerStyle} placeholder={placeholder}>
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
            >
              {triggerLabel}
            </Text>
          )}
        </Flex>
      </Select.Trigger>
      <Select.Content position={contentPosition}>
        {options.map((option) => (
          <Select.Item 
            key={option.value} 
            value={option.value}
            disabled={option.disabled}
          >
            <Flex align="center" gap="2" justify="between" className="select-option-row">
              <Flex align="center" gap="2" className="select-option-row__main">
                {option.prefix}
                {option.label}
              </Flex>
              {option.suffix}
            </Flex>
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  );

  if (!label) {
    return selectControl;
  }

  if (layout === "horizontal") {
    return (
      <Flex align="center" gap={gap}>
        <Text 
          size={labelSize} 
          weight={labelWeight}
        >
          {label}
        </Text>
        {selectControl}
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={gap}>
      <Text 
        size={labelSize} 
        weight={labelWeight}
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
}: Omit<
  LabeledSelectProps,
  | "label"
  | "labelSize"
  | "labelWeight"
  | "labelColor"
  | "layout"
  | "gap"
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
      <Select.Trigger className={triggerClassName} style={triggerStyle} placeholder={placeholder}>
        <Flex align="center" gap="2" className="select-trigger-content">
          {triggerPrefix}
          {selectedOption?.prefix}
          {triggerLabel && (
            <Text size={size} color={selectedOption ? undefined : "gray"} className="select-option-label">
              {triggerLabel}
            </Text>
          )}
        </Flex>
      </Select.Trigger>
      <Select.Content position={contentPosition}>
        {options.map((option) => (
          <Select.Item 
            key={option.value} 
            value={option.value}
            disabled={option.disabled}
          >
            <Flex align="center" gap="2" justify="between" className="select-option-row">
              <Flex align="center" gap="2" className="select-option-row__main">
                {option.prefix}
                {option.label}
              </Flex>
              {option.suffix}
            </Flex>
          </Select.Item>
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
  searchPlaceholder = "Search...",
  emptyMessage = "No matching options",
  contentHeight = 260,
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const selectedOption = options.find((opt) => opt.value === value);

  const filteredOptions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return options;

    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(query) ||
        option.value.toLowerCase().includes(query)
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
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
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
          <Flex align="center" gap="2" className="select-trigger-content">
            {selectedOption?.prefix}
            <Text
              size={size}
              color={selectedOption ? undefined : "gray"}
              className="select-option-label"
            >
              {selectedOption?.label || placeholder}
            </Text>
          </Flex>
          <ChevronDown size={16} aria-hidden="true" />
        </Button>
      </Popover.Trigger>

      <Popover.Content
        align="start"
        data-slot="searchable-select-content"
        className="searchable-select-content"
        style={{ width: "var(--radix-popover-trigger-width)" }}
      >
        <Box p="2" className="searchable-select-search-box">
          <TextField.Root
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={searchPlaceholder}
            autoFocus
            size={size}
          >
            <TextField.Slot>
              <Search size={16} aria-hidden="true" />
            </TextField.Slot>
          </TextField.Root>
        </Box>

        <ScrollArea style={{ height: contentHeight }}>
          <Flex direction="column" py="1">
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
                  <Flex align="center" gap="2" justify="between" className="select-option-row">
                    <Flex align="center" gap="2" className="select-option-row__main select-option-row__main--truncate">
                      {option.prefix}
                      <Text size="2" truncate>
                        {option.label}
                      </Text>
                    </Flex>
                    {option.suffix}
                  </Flex>
                </button>
              ))
            ) : (
              <Flex align="center" justify="center" p="4">
                <Text size="2" color="gray">
                  {emptyMessage}
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
      <Flex align="center" gap={gap}>
        <Text size={labelSize} weight={labelWeight} color={labelColor}>
          {label}
        </Text>
        {selectControl}
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={gap}>
      <Text size={labelSize} weight={labelWeight} color={labelColor}>
        {label}
      </Text>
      {selectControl}
    </Flex>
  );
}
