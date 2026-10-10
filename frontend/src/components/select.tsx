/**
 * Labeled Select Component
 *
 * 通用的带标签的下拉选择组件，封装了 Radix UI Select 组件。
 * 提供一致的样式和用户体验。
 */

import {
  Box,
  Button,
  ChevronDownIcon,
  Flex,
  Popover,
  ScrollArea,
  Select,
  Text,
  TextField,
} from "@radix-ui/themes";
import clsx from "clsx";
import { Check, ChevronDown, Search } from "lucide-react";
import { Fragment, useCallback, useMemo, useRef, useState } from "react";
import type { CSSProperties, FocusEventHandler, ReactNode, ComponentProps } from "react";
import { useTranslation } from "react-i18next";

import { useAppShell } from "@/features/app-shell/components/app-shell-context";

import { MobileSelectSheet } from "./mobile-select-sheet";

import "./select.css";

type TextColor = ComponentProps<typeof Text>["color"];

export interface SelectOption {
  value: string;
  label: string;
  prefix?: ReactNode;
  suffix?: ReactNode;
  /** Dropdown-only controls; provide accessible names and type="button" on buttons. */
  actions?: ReactNode;
  description?: string;
  labelColor?: string;
  fontFamily?: string;
  disabled?: boolean;
  separatorAfter?: boolean;
}

function SelectOptionWithActions({
  option,
  children,
  onAction,
}: {
  option: SelectOption;
  children: ReactNode;
  onAction: () => void;
}) {
  const rowRef = useRef<HTMLDivElement>(null);
  if (!option.actions) return children;

  return (
    <div
      ref={rowRef}
      data-slot="select-option-with-actions"
      onKeyDownCapture={(event) => {
        const row = rowRef.current;
        if (!row) return;
        const actions = row.querySelector<HTMLElement>('[data-slot="select-option-actions"]');
        const isAction = actions?.contains(event.target as Node);
        if (!isAction && (event.key === "ArrowRight" || (event.key === "Tab" && !event.shiftKey))) {
          const control = actions?.querySelector<HTMLElement>(
            'button:not(:disabled), a[href], input:not(:disabled), [tabindex]:not([tabindex="-1"])',
          );
          if (!control) return;
          event.preventDefault();
          event.stopPropagation();
          control.focus();
        } else if (isAction && event.key === "ArrowLeft") {
          event.preventDefault();
          event.stopPropagation();
          row
            .querySelector<HTMLElement>(
              '[role="option"], [data-slot="searchable-select-item"], [data-slot="mobile-select-item"]',
            )
            ?.focus();
        }
      }}
    >
      {children}
      <div
        role="group"
        aria-label={option.label}
        data-slot="select-option-actions"
        onClickCapture={(event) => {
          if (
            (event.target as HTMLElement).closest('button:not(:disabled), a[href], [role="button"]')
          ) {
            onAction();
          }
        }}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onPointerMove={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key !== "Escape") event.stopPropagation();
        }}
      >
        {option.actions}
      </div>
    </div>
  );
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

interface MobileSelectOptionListProps {
  options: SelectOption[];
  value: string | undefined;
  size: "1" | "2" | "3";
  onSelect: (value: string) => void;
  onAction: () => void;
}

function MobileSelectOptionList({
  options,
  value,
  size,
  onSelect,
  onAction,
}: MobileSelectOptionListProps) {
  return (
    <div className="mobile-select-option-list">
      {options.map((option) => {
        const isSelected = option.value === value;

        return (
          <Fragment key={option.value}>
            <SelectOptionWithActions
              option={option}
              onAction={onAction}
            >
              <button
                type="button"
                disabled={option.disabled}
                data-slot="mobile-select-item"
                data-state={isSelected ? "checked" : "unchecked"}
                aria-pressed={isSelected}
                className="mobile-select-item"
                onClick={() => onSelect(option.value)}
              >
                <SelectOptionContent
                  option={option}
                  size={size}
                />
                {isSelected ? (
                  <Check
                    size={16}
                    aria-hidden="true"
                    className="mobile-select-item__check"
                  />
                ) : null}
              </button>
            </SelectOptionWithActions>
            {option.separatorAfter ? <div className="mobile-select-separator" /> : null}
          </Fragment>
        );
      })}
    </div>
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
  onContentFocusCapture?: FocusEventHandler<HTMLDivElement>;
  onContentCloseAutoFocus?: ComponentProps<typeof Select.Content>["onCloseAutoFocus"];
  keepFocusOnTouch?: boolean;
  onTouchTrigger?: () => void;
  preventContentFocus?: boolean;
  variant?: "default" | "icon";
  triggerAriaLabel?: string;
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
  onContentFocusCapture,
  onContentCloseAutoFocus,
  keepFocusOnTouch = false,
  onTouchTrigger,
  preventContentFocus = false,
  variant = "default",
  triggerAriaLabel,
}: LabeledSelectProps) {
  const { t } = useTranslation();
  const { isMobile } = useAppShell();
  const [isOpen, setIsOpen] = useState(false);
  const actionCloseRef = useRef(false);
  const hasActions = options.some((option) => Boolean(option.actions));
  const triggerPointerTypeRef = useRef<string | null>(null);
  const shouldKeepFocusOnTouch = keepFocusOnTouch && Boolean(onTouchTrigger);
  const selectedOption = options.find((opt) => opt.value === value);
  const triggerLabel = selectedOption?.label || placeholder;
  const isIconVariant = variant === "icon";
  const isTriggerLabelVisible = !isIconVariant && triggerLabelVisible;

  const handleTriggerPointerDown = useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      triggerPointerTypeRef.current = event.pointerType;
      if (
        !shouldKeepFocusOnTouch ||
        (event.pointerType !== "touch" && event.pointerType !== "pen")
      ) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      onTouchTrigger?.();
    },
    [onTouchTrigger, shouldKeepFocusOnTouch],
  );

  const handleTriggerClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      const pointerType = triggerPointerTypeRef.current;
      triggerPointerTypeRef.current = null;
      if (!shouldKeepFocusOnTouch || (pointerType !== "touch" && pointerType !== "pen")) {
        return;
      }

      event.preventDefault();
      onTouchTrigger?.();
      setIsOpen((open) => !open);
    },
    [onTouchTrigger, shouldKeepFocusOnTouch],
  );

  const handleContentRef = useCallback(
    (content: HTMLDivElement | null) => {
      if (!content || !preventContentFocus) return;

      content.setAttribute("inert", "");
      window.setTimeout(() => content.removeAttribute("inert"), 0);
    },
    [preventContentFocus],
  );

  const selectControl = (
    <Select.Root
      value={value || undefined}
      onValueChange={onChange}
      disabled={disabled}
      open={shouldKeepFocusOnTouch || hasActions ? isOpen : undefined}
      onOpenChange={
        shouldKeepFocusOnTouch || hasActions
          ? (open) => {
              if (open) actionCloseRef.current = false;
              setIsOpen(open);
            }
          : undefined
      }
      size={size}
    >
      <Select.Trigger
        className={clsx(
          !isIconVariant && "select-trigger--background",
          isIconVariant && "select-trigger--icon",
          triggerClassName,
        )}
        style={
          selectedOption?.labelColor
            ? ({
                "--select-label-color": selectedOption.labelColor,
                ...triggerStyle,
              } as CSSProperties)
            : triggerStyle
        }
        placeholder={placeholder}
        aria-label={triggerAriaLabel ?? label ?? triggerLabel}
        onPointerDown={handleTriggerPointerDown}
        onClick={handleTriggerClick}
      >
        <Flex
          align="center"
          justify={isTriggerLabelVisible ? undefined : "center"}
          gap={isTriggerLabelVisible ? "2" : "0"}
          className={isTriggerLabelVisible ? undefined : "select-trigger-content--icon-only"}
        >
          {triggerPrefix}
          {selectedOption?.prefix}
          {isTriggerLabelVisible && triggerLabel && (
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
        ref={handleContentRef}
        position={contentPosition}
        className={contentClassName}
        onFocusCapture={onContentFocusCapture}
        onCloseAutoFocus={(event) => {
          onContentCloseAutoFocus?.(event);
          if (actionCloseRef.current) event.preventDefault();
        }}
      >
        {options.map((option) => (
          <Fragment key={option.value}>
            <SelectOptionWithActions
              option={option}
              onAction={() => {
                actionCloseRef.current = true;
                setIsOpen(false);
              }}
            >
              <Select.Item
                value={option.value}
                disabled={option.disabled}
                onPointerDown={(event) => {
                  if (
                    shouldKeepFocusOnTouch &&
                    !option.disabled &&
                    (event.pointerType === "touch" || event.pointerType === "pen")
                  ) {
                    event.preventDefault();
                    onChange(option.value);
                    onTouchTrigger?.();
                    setIsOpen(false);
                  }
                }}
              >
                <SelectOptionContent
                  option={option}
                  size={size}
                />
              </Select.Item>
            </SelectOptionWithActions>
            {option.separatorAfter ? <Select.Separator /> : null}
          </Fragment>
        ))}
      </Select.Content>
    </Select.Root>
  );

  const mobileSelectControl = (
    <MobileSelectSheet
      open={isOpen}
      onOpenChange={(open) => {
        if (open) actionCloseRef.current = false;
        setIsOpen(open);
      }}
      title={label ?? placeholder ?? t("select.title")}
      trigger={
        <button
          type="button"
          disabled={disabled}
          className={clsx(
            "rt-reset",
            "rt-SelectTrigger",
            `rt-r-size-${size}`,
            "rt-variant-surface",
            !isIconVariant && "select-trigger--background",
            isIconVariant && "select-trigger--icon",
            triggerClassName,
          )}
          style={
            selectedOption?.labelColor
              ? ({
                  "--select-label-color": selectedOption.labelColor,
                  ...triggerStyle,
                } as CSSProperties)
              : triggerStyle
          }
          aria-label={triggerAriaLabel ?? label ?? triggerLabel}
          data-state={isOpen ? "open" : "closed"}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          onPointerDown={handleTriggerPointerDown}
        >
          <span className="rt-SelectTriggerInner">
            <Flex
              align="center"
              justify={isTriggerLabelVisible ? undefined : "center"}
              gap={isTriggerLabelVisible ? "2" : "0"}
              className={isTriggerLabelVisible ? undefined : "select-trigger-content--icon-only"}
            >
              {triggerPrefix}
              {selectedOption?.prefix}
              {isTriggerLabelVisible && triggerLabel && (
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
          </span>
          <ChevronDownIcon
            aria-hidden="true"
            className="rt-SelectIcon"
          />
        </button>
      }
    >
      <MobileSelectOptionList
        options={options}
        value={value}
        size={size}
        onSelect={(nextValue) => {
          onChange(nextValue);
          onTouchTrigger?.();
          setIsOpen(false);
        }}
        onAction={() => {
          actionCloseRef.current = true;
          setIsOpen(false);
        }}
      />
    </MobileSelectSheet>
  );

  const renderedSelectControl = isMobile ? mobileSelectControl : selectControl;

  if (!label) {
    return renderedSelectControl;
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
        {renderedSelectControl}
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
      {renderedSelectControl}
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
  triggerLabelVisible = true,
  variant = "default",
  triggerAriaLabel,
}: Omit<
  LabeledSelectProps,
  "label" | "labelSize" | "labelWeight" | "labelColor" | "layout" | "gap"
>) {
  const { t } = useTranslation();
  const { isMobile } = useAppShell();
  const [isOpen, setIsOpen] = useState(false);
  const actionCloseRef = useRef(false);
  const hasActions = options.some((option) => Boolean(option.actions));
  const selectedOption = options.find((opt) => opt.value === value);
  const triggerLabel = selectedOption?.label || placeholder;
  const isIconVariant = variant === "icon";
  const isTriggerLabelVisible = !isIconVariant && triggerLabelVisible;

  const selectControl = (
    <Select.Root
      value={value || undefined}
      onValueChange={onChange}
      disabled={disabled}
      size={size}
      open={hasActions ? isOpen : undefined}
      onOpenChange={
        hasActions
          ? (open) => {
              if (open) actionCloseRef.current = false;
              setIsOpen(open);
            }
          : undefined
      }
    >
      <Select.Trigger
        className={clsx(
          !isIconVariant && "select-trigger--background",
          isIconVariant && "select-trigger--icon",
          triggerClassName,
        )}
        style={
          selectedOption?.labelColor
            ? ({
                "--select-label-color": selectedOption.labelColor,
                ...triggerStyle,
              } as CSSProperties)
            : triggerStyle
        }
        placeholder={placeholder}
        aria-label={triggerAriaLabel ?? triggerLabel}
      >
        <Flex
          align="center"
          justify={isTriggerLabelVisible ? undefined : "center"}
          gap={isTriggerLabelVisible ? "2" : "0"}
          className={
            isTriggerLabelVisible ? "select-trigger-content" : "select-trigger-content--icon-only"
          }
        >
          {triggerPrefix}
          {selectedOption?.prefix}
          {isTriggerLabelVisible && triggerLabel && (
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
        onCloseAutoFocus={(event) => {
          if (actionCloseRef.current) event.preventDefault();
        }}
      >
        {options.map((option) => (
          <Fragment key={option.value}>
            <SelectOptionWithActions
              option={option}
              onAction={() => {
                actionCloseRef.current = true;
                setIsOpen(false);
              }}
            >
              <Select.Item
                value={option.value}
                disabled={option.disabled}
              >
                <SelectOptionContent
                  option={option}
                  size={size}
                />
              </Select.Item>
            </SelectOptionWithActions>
            {option.separatorAfter ? <Select.Separator /> : null}
          </Fragment>
        ))}
      </Select.Content>
    </Select.Root>
  );

  const mobileSelectControl = (
    <MobileSelectSheet
      open={isOpen}
      onOpenChange={(open) => {
        if (open) actionCloseRef.current = false;
        setIsOpen(open);
      }}
      title={placeholder ?? t("select.title")}
      trigger={
        <button
          type="button"
          disabled={disabled}
          className={clsx(
            "rt-reset",
            "rt-SelectTrigger",
            `rt-r-size-${size}`,
            "rt-variant-surface",
            !isIconVariant && "select-trigger--background",
            isIconVariant && "select-trigger--icon",
            triggerClassName,
          )}
          style={
            selectedOption?.labelColor
              ? ({
                  "--select-label-color": selectedOption.labelColor,
                  ...triggerStyle,
                } as CSSProperties)
              : triggerStyle
          }
          aria-label={triggerAriaLabel ?? triggerLabel}
          data-state={isOpen ? "open" : "closed"}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
        >
          <span className="rt-SelectTriggerInner">
            <Flex
              align="center"
              justify={isTriggerLabelVisible ? undefined : "center"}
              gap={isTriggerLabelVisible ? "2" : "0"}
              className={
                isTriggerLabelVisible
                  ? "select-trigger-content"
                  : "select-trigger-content--icon-only"
              }
            >
              {triggerPrefix}
              {selectedOption?.prefix}
              {isTriggerLabelVisible && triggerLabel && (
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
          </span>
          <ChevronDownIcon
            aria-hidden="true"
            className="rt-SelectIcon"
          />
        </button>
      }
    >
      <MobileSelectOptionList
        options={options}
        value={value}
        size={size}
        onSelect={(nextValue) => {
          onChange(nextValue);
          setIsOpen(false);
        }}
        onAction={() => {
          actionCloseRef.current = true;
          setIsOpen(false);
        }}
      />
    </MobileSelectSheet>
  );

  return isMobile ? mobileSelectControl : selectControl;
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
  const { isMobile } = useAppShell();
  const [open, setOpen] = useState(false);
  const actionCloseRef = useRef(false);
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
    if (nextOpen) actionCloseRef.current = false;
    if (!nextOpen) setSearchQuery("");
    setOpen(nextOpen);
  };

  const handleSelect = (nextValue: string) => {
    onChange(nextValue);
    setOpen(false);
    setSearchQuery("");
  };

  const trigger = (
    <Button
      type="button"
      variant="surface"
      color="gray"
      disabled={disabled}
      className="select-trigger--background"
      data-slot="searchable-select-trigger"
      data-state={open ? "open" : "closed"}
      aria-expanded={open}
      aria-haspopup="listbox"
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
  );

  const searchableContent = (
    <>
      <Box
        p="2"
        className="searchable-select-search-box"
      >
        <TextField.Root
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder={resolvedSearchPlaceholder}
          autoFocus={!isMobile}
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

      {isMobile ? (
        filteredOptions.length > 0 ? (
          <MobileSelectOptionList
            options={filteredOptions}
            value={value}
            size={size}
            onSelect={handleSelect}
            onAction={() => {
              actionCloseRef.current = true;
              handleOpenChange(false);
            }}
          />
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
        )
      ) : (
        <ScrollArea style={{ height: contentHeight }}>
          <Flex
            direction="column"
            py="1"
          >
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <SelectOptionWithActions
                  key={option.value}
                  option={option}
                  onAction={() => {
                    actionCloseRef.current = true;
                    handleOpenChange(false);
                  }}
                >
                  <button
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
                </SelectOptionWithActions>
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
      )}
    </>
  );

  const selectControl = (
    <Popover.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Popover.Trigger>{trigger}</Popover.Trigger>
      <Popover.Content
        align="start"
        data-slot="searchable-select-content"
        className="searchable-select-content"
        onCloseAutoFocus={(event) => {
          if (actionCloseRef.current) event.preventDefault();
        }}
        style={{ width: "var(--radix-popover-trigger-width)" }}
      >
        {searchableContent}
      </Popover.Content>
    </Popover.Root>
  );

  const mobileSelectControl = (
    <MobileSelectSheet
      open={open}
      onOpenChange={handleOpenChange}
      title={label ?? placeholder ?? t("select.title")}
      trigger={trigger}
      contentClassName="searchable-select-sheet-content"
    >
      {searchableContent}
    </MobileSelectSheet>
  );

  const renderedSelectControl = isMobile ? mobileSelectControl : selectControl;

  if (!label) {
    return renderedSelectControl;
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
        {renderedSelectControl}
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
      {renderedSelectControl}
    </Flex>
  );
}
