/**
 * Multi Select Field Component
 *
 * 通用多选字段，使用标签展示已选项，支持在标签内直接取消选择。
 */

import { Checkbox, Popover, ScrollArea, Text } from "@radix-ui/themes";
import { ChevronDown, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { ComponentProps, CSSProperties, KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import "./multi-select-field.css";

export interface MultiSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface MultiSelectFieldProps {
  options: MultiSelectOption[];
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
  emptyMessage?: string;
  label?: string;
  labelSize?: "1" | "2" | "3";
  labelWeight?: "regular" | "medium" | "bold";
  labelColor?: ComponentProps<typeof Text>["color"];
  triggerStyle?: CSSProperties;
}

export function MultiSelectField({
  options,
  value,
  onChange,
  disabled = false,
  placeholder,
  emptyMessage,
  label,
  labelSize = "2",
  labelWeight = "medium",
  labelColor,
  triggerStyle,
}: MultiSelectFieldProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const selectedOptions = useMemo(() => {
    const selected = new Set(value);
    return options.filter((option) => selected.has(option.value));
  }, [options, value]);

  const handleToggle = (optionValue: string) => {
    if (disabled) return;
    if (value.includes(optionValue)) {
      onChange(value.filter((item) => item !== optionValue));
      return;
    }
    onChange([...value, optionValue]);
  };

  const handleRemove = (optionValue: string) => {
    if (disabled) return;
    onChange(value.filter((item) => item !== optionValue));
  };

  const handleRemoveKeyDown = (event: KeyboardEvent<HTMLSpanElement>, optionValue: string) => {
    if (disabled) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      event.stopPropagation();
      handleRemove(optionValue);
    }
  };

  return (
    <div>
      {label ? (
        <Text
          as="label"
          size={labelSize}
          weight={labelWeight}
          color={labelColor}
          mb="1"
          className="multi-select-field__label"
        >
          {label}
        </Text>
      ) : null}

      <Popover.Root
        open={open}
        onOpenChange={(nextOpen) => {
          if (!disabled) setOpen(nextOpen);
        }}
      >
        <Popover.Trigger>
          <div
            className="multi-select-field__trigger"
            style={triggerStyle}
            data-disabled={disabled ? "true" : "false"}
          >
            <div className="multi-select-field__value">
              {selectedOptions.length > 0 ? (
                selectedOptions.map((option) => (
                  <span
                    key={option.value}
                    className="multi-select-field__tag"
                  >
                    <span className="multi-select-field__tag-label">{option.label}</span>
                    <span
                      role="button"
                      tabIndex={disabled ? -1 : 0}
                      className="multi-select-field__tag-remove"
                      aria-label={t("multiSelect.removeOption", { label: option.label })}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRemove(option.value);
                      }}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                      }}
                      onKeyDown={(event) => handleRemoveKeyDown(event, option.value)}
                    >
                      <X size={12} />
                    </span>
                  </span>
                ))
              ) : (
                <span className="multi-select-field__placeholder">
                  {placeholder ?? t("multiSelect.placeholder")}
                </span>
              )}
            </div>

            <span className="multi-select-field__chevron">
              <ChevronDown size={16} />
            </span>
          </div>
        </Popover.Trigger>

        <Popover.Content
          className="multi-select-field__content"
          align="start"
          side="bottom"
        >
          {options.length > 0 ? (
            <ScrollArea className="multi-select-field__options">
              <div className="multi-select-field__options-inner">
                {options.map((option) => {
                  const checked = value.includes(option.value);
                  return (
                    <label
                      key={option.value}
                      className="multi-select-field__option"
                      data-disabled={option.disabled ? "true" : "false"}
                    >
                      <Checkbox
                        checked={checked}
                        disabled={disabled || option.disabled}
                        onCheckedChange={() => handleToggle(option.value)}
                      />
                      <span className="multi-select-field__option-label">{option.label}</span>
                    </label>
                  );
                })}
              </div>
            </ScrollArea>
          ) : (
            <Text
              size="2"
              color="gray"
              className="multi-select-field__empty"
            >
              {emptyMessage ?? t("multiSelect.empty")}
            </Text>
          )}
        </Popover.Content>
      </Popover.Root>
    </div>
  );
}
