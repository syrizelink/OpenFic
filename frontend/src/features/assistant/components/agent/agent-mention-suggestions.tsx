import {
  BookOpen,
  FileText,
  Folder,
  Package,
  ScrollText,
  NotebookText,
  UserRound,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";

import type {
  AgentComposerSuggestionItem,
  AgentComposerSuggestionMode,
  AgentComposerSuggestionStatus,
} from "./agent-composer-editor";

interface AgentMentionSuggestionsProps {
  clearanceHeight: number;
  mode: AgentComposerSuggestionMode;
  items: AgentComposerSuggestionItem[];
  selectedIndex: number;
  status: AgentComposerSuggestionStatus;
  visible: boolean;
  onSelect: (item: AgentComposerSuggestionItem, index: number) => void;
  onSelectedIndexChange: (index: number) => void;
  onClose: () => void;
}

function getItemIcon(kind: AgentComposerSuggestionItem["kind"]) {
  if (kind === "skill") return <Package size={14} />;
  if (kind === "volume") return <BookOpen size={14} />;
  if (kind === "note") return <NotebookText size={14} />;
  if (kind === "note_category") return <Folder size={14} />;
  if (kind === "world_info_entry") return <ScrollText size={14} />;
  if (kind === "character") return <UserRound size={14} />;
  return <FileText size={14} />;
}

function getItemMeta(
  item: AgentComposerSuggestionItem,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (item.kind === "skill") return item.description;

  const base =
    item.kind === "volume"
      ? t("assistant.mentionKind.volume")
      : item.kind === "note"
        ? t("assistant.mentionKind.note")
        : item.kind === "note_category"
          ? t("assistant.mentionKind.noteCategory")
          : item.kind === "world_info_entry"
            ? t("assistant.mentionKind.worldInfoEntry")
            : item.kind === "character"
              ? t("assistant.mentionKind.character")
              : t("assistant.mentionKind.chapter");
  return item.description
    ? t("assistant.mentionMetaFormat", { base, description: item.description })
    : base;
}

function getStateMessage(
  status: AgentComposerSuggestionStatus,
  mode: AgentComposerSuggestionMode,
  t: (key: string) => string,
): string {
  if (mode === "command") {
    if (status === "loading") return t("assistant.commandSearch.loading");
    if (status === "empty") return t("assistant.mentionSearch.empty");
    return t("assistant.commandSearch.prompt");
  }
  const keyPrefix = "assistant.mentionSearch";
  if (status === "idle") return t(`${keyPrefix}.idle`);
  if (status === "loading") return t(`${keyPrefix}.loading`);
  return t(`${keyPrefix}.empty`);
}

export function AgentMentionSuggestions({
  clearanceHeight,
  mode,
  items,
  selectedIndex,
  status,
  visible,
  onSelect,
  onSelectedIndexChange,
  onClose,
}: AgentMentionSuggestionsProps) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLDivElement>(null);
  const shouldScrollSelectionRef = useRef(false);
  const normalizedClearanceHeight = Math.max(clearanceHeight, 0);
  const style = {
    "--ai-sidebar-mention-clearance-height": `${normalizedClearanceHeight}px`,
  } as CSSProperties;

  useEffect(() => {
    if (!visible || status !== "ready" || !listRef.current || !shouldScrollSelectionRef.current) {
      return;
    }
    const element = listRef.current.querySelector<HTMLElement>(
      `[data-suggestion-index="${selectedIndex}"]`,
    );
    element?.scrollIntoView({ block: "nearest" });
    shouldScrollSelectionRef.current = false;
  }, [selectedIndex, status, visible]);

  const handleSelectedIndexChange = useCallback(
    (index: number) => {
      shouldScrollSelectionRef.current = true;
      onSelectedIndexChange(index);
    },
    [onSelectedIndexChange],
  );

  const handleMouseEnter = useCallback(
    (index: number) => {
      shouldScrollSelectionRef.current = false;
      onSelectedIndexChange(index);
    },
    [onSelectedIndexChange],
  );

  useEffect(() => {
    if (!visible) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      const hasSelectableItems = status === "ready" && items.length > 0;
      switch (event.key) {
        case "ArrowDown":
          if (!hasSelectableItems) break;
          event.preventDefault();
          event.stopPropagation();
          handleSelectedIndexChange((selectedIndex + 1) % items.length);
          break;
        case "ArrowUp":
          if (!hasSelectableItems) break;
          event.preventDefault();
          event.stopPropagation();
          handleSelectedIndexChange((selectedIndex - 1 + items.length) % items.length);
          break;
        case "Enter":
        case "Tab":
          if (!hasSelectableItems || selectedIndex < 0) break;
          event.preventDefault();
          event.stopPropagation();
          onSelect(items[selectedIndex], selectedIndex);
          break;
        case "Escape":
          event.preventDefault();
          event.stopPropagation();
          onClose();
          break;
      }
    };

    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [handleSelectedIndexChange, items, onClose, onSelect, selectedIndex, status, visible]);

  if (!visible) return null;

  const hasCommandGroup = mode === "command" && status === "ready" && items.length > 0;
  const suggestionContent =
    status === "ready" && items.length > 0 ? (
      <div
        ref={listRef}
        className="agent-mention-suggestions-list"
      >
        {hasCommandGroup && (
          <div className="agent-command-suggestion-header">{t("assistant.commandKind.skill")}</div>
        )}
        {items.map((item, index) => (
          <button
            key={`${item.kind}-${item.id}`}
            type="button"
            className="agent-mention-suggestion-item"
            data-suggestion-index={index}
            data-selected={index === selectedIndex}
            onClick={() => onSelect(item, index)}
            onMouseEnter={() => handleMouseEnter(index)}
          >
            <span
              className="agent-mention-suggestion-icon"
              aria-hidden="true"
            >
              {getItemIcon(item.kind)}
            </span>
            <span className="agent-mention-suggestion-copy">
              <span className="agent-mention-suggestion-title">
                {item.kind === "skill" ? item.name : item.title}
              </span>
              <span className="agent-mention-suggestion-kind">{getItemMeta(item, t)}</span>
            </span>
          </button>
        ))}
        {hasCommandGroup && (
          <div
            className="agent-command-suggestion-divider"
            aria-hidden="true"
          />
        )}
      </div>
    ) : (
      <div className="agent-mention-suggestion-state">{getStateMessage(status, mode, t)}</div>
    );

  return (
    <div
      className="ai-sidebar-mention-shell"
      style={style}
    >
      <div className="ai-sidebar-mention-card-stack">
        <div
          className="ai-sidebar-mention-card"
          data-variant={mode}
        >
          <motion.div
            className="ai-sidebar-mention-card-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            {suggestionContent}
          </motion.div>
          <div
            aria-hidden="true"
            className="ai-sidebar-mention-card-clearance"
          />
        </div>
      </div>
    </div>
  );
}
