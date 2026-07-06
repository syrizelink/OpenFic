/**
 * AutocompletePopover - 通用自动补全弹出面板
 *
 * 用于在编辑器中显示补全建议列表。
 * 风格参考 VSCode 补全面板。
 */

import { Box } from "@radix-ui/themes";
import { useEffect, useRef, useCallback } from "react";

import "./autocomplete-popover.css";

export interface AutocompleteItem {
  /** 显示标签 */
  label: string;
  /** 插入文本 */
  insertText: string;
  /** 描述（可选，显示在右侧） */
  description?: string;
  /** 图标（可选） */
  icon?: React.ReactNode;
  /** 插入后光标偏移（负数表示向左移动） */
  cursorOffset?: number;
}

export interface AutocompletePopoverProps {
  /** 补全项列表 */
  items: AutocompleteItem[];
  /** 锚点位置（相对于视口） */
  anchorRect: { top: number; left: number } | null;
  /** 是否可见 */
  visible: boolean;
  /** 当前选中索引 */
  selectedIndex: number;
  /** 选择某项时的回调 */
  onSelect: (item: AutocompleteItem, index: number) => void;
  /** 选中索引变化回调 */
  onSelectedIndexChange: (index: number) => void;
  /** 关闭回调 */
  onClose: () => void;
  /** 无固定项时显示的提示 */
  hint?: string;
  /** 当前输入的过滤文本（用于高亮） */
  filterText?: string;
}

/** 高亮显示匹配文本 */
function HighlightedLabel({ label, filterText }: { label: string; filterText?: string }) {
  if (!filterText) {
    return <span>{label}</span>;
  }

  const lowerLabel = label.toLowerCase();
  const lowerFilter = filterText.toLowerCase();
  const matchIndex = lowerLabel.indexOf(lowerFilter);

  if (matchIndex === -1) {
    return <span>{label}</span>;
  }

  const before = label.slice(0, matchIndex);
  const match = label.slice(matchIndex, matchIndex + filterText.length);
  const after = label.slice(matchIndex + filterText.length);

  return (
    <span>
      {before}
      <span className="highlight">{match}</span>
      {after}
    </span>
  );
}

export function AutocompletePopover({
  items,
  anchorRect,
  visible,
  selectedIndex,
  onSelect,
  onSelectedIndexChange,
  onClose,
  hint,
  filterText,
}: AutocompletePopoverProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // 滚动选中项到可视区域
  useEffect(() => {
    if (!listRef.current || items.length === 0) return;

    const selectedEl = listRef.current.children[selectedIndex] as HTMLElement;
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex, items.length]);

  // 键盘事件处理
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          e.stopPropagation();
          if (items.length > 0) {
            onSelectedIndexChange((selectedIndex + 1) % items.length);
          }
          break;

        case "ArrowUp":
          e.preventDefault();
          e.stopPropagation();
          if (items.length > 0) {
            onSelectedIndexChange((selectedIndex - 1 + items.length) % items.length);
          }
          break;

        case "Enter":
        case "Tab":
          if (items.length > 0 && selectedIndex >= 0) {
            e.preventDefault();
            e.stopPropagation();
            onSelect(items[selectedIndex], selectedIndex);
          }
          break;

        case "Escape":
          e.preventDefault();
          e.stopPropagation();
          onClose();
          break;
      }
    },
    [visible, items, selectedIndex, onSelect, onSelectedIndexChange, onClose],
  );

  // 添加/移除键盘监听
  useEffect(() => {
    if (visible) {
      document.addEventListener("keydown", handleKeyDown, true);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [visible, handleKeyDown]);

  if (!visible || !anchorRect) return null;

  const hasItems = items.length > 0;
  const showHint = !hasItems && hint;

  return (
    <Box
      ref={containerRef}
      className="autocomplete-popover"
      style={{
        position: "fixed",
        top: anchorRect.top,
        left: anchorRect.left,
        zIndex: 9999,
      }}
    >
      {showHint ? (
        <div className="autocomplete-hint">{hint}</div>
      ) : hasItems ? (
        <div
          ref={listRef}
          className="autocomplete-list"
        >
          {items.map((item, index) => (
            <div
              key={`${item.label}-${index}`}
              className={`autocomplete-item ${index === selectedIndex ? "selected" : ""}`}
              onClick={() => onSelect(item, index)}
              onMouseEnter={() => onSelectedIndexChange(index)}
            >
              {item.icon && <span className="autocomplete-item-icon">{item.icon}</span>}
              <span className="autocomplete-item-label">
                <HighlightedLabel
                  label={item.label}
                  filterText={filterText}
                />
              </span>
              {item.description && (
                <span className="autocomplete-item-desc">{item.description}</span>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </Box>
  );
}
