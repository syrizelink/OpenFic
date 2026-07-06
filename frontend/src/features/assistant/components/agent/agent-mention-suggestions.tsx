import { BookOpen, FileText, Folder, StickyNote } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";

import type { AssistantMentionCandidate } from "@/features/assistant/lib/mention-text";

import type { AgentComposerSuggestionStatus } from "./agent-composer-editor";

interface AgentMentionSuggestionsProps {
  clearanceHeight: number;
  items: AssistantMentionCandidate[];
  selectedIndex: number;
  status: AgentComposerSuggestionStatus;
  visible: boolean;
  onSelect: (item: AssistantMentionCandidate, index: number) => void;
  onSelectedIndexChange: (index: number) => void;
  onClose: () => void;
}

function getItemIcon(kind: AssistantMentionCandidate["kind"]) {
  if (kind === "volume") return <BookOpen size={12} />;
  if (kind === "note") return <StickyNote size={12} />;
  if (kind === "note_category") return <Folder size={12} />;
  return <FileText size={12} />;
}

function getItemMeta(
  item: AssistantMentionCandidate,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const base =
    item.kind === "volume"
      ? t("assistant.mentionKind.volume")
      : item.kind === "note"
        ? t("assistant.mentionKind.note")
        : item.kind === "note_category"
          ? t("assistant.mentionKind.noteCategory")
          : t("assistant.mentionKind.chapter");
  return item.description
    ? t("assistant.mentionMetaFormat", { base, description: item.description })
    : base;
}

function getStateMessage(
  status: AgentComposerSuggestionStatus,
  t: (key: string) => string,
): string {
  if (status === "idle") return t("assistant.mentionSearch.idle");
  if (status === "loading") return t("assistant.mentionSearch.loading");
  return t("assistant.mentionSearch.empty");
}

export function AgentMentionSuggestions({
  clearanceHeight,
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
  const normalizedClearanceHeight = Math.max(clearanceHeight, 0);
  const style = {
    "--ai-sidebar-mention-clearance-height": `${normalizedClearanceHeight}px`,
  } as CSSProperties;

  useEffect(() => {
    if (!visible || status !== "ready" || !listRef.current) return;
    const element = listRef.current.children[selectedIndex] as HTMLElement | undefined;
    element?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex, status, visible]);

  useEffect(() => {
    if (!visible) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      const hasSelectableItems = status === "ready" && items.length > 0;
      switch (event.key) {
        case "ArrowDown":
          if (!hasSelectableItems) break;
          event.preventDefault();
          event.stopPropagation();
          onSelectedIndexChange((selectedIndex + 1) % items.length);
          break;
        case "ArrowUp":
          if (!hasSelectableItems) break;
          event.preventDefault();
          event.stopPropagation();
          onSelectedIndexChange((selectedIndex - 1 + items.length) % items.length);
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
  }, [items, onClose, onSelect, onSelectedIndexChange, selectedIndex, status, visible]);

  if (!visible) return null;

  return (
    <div
      className="ai-sidebar-mention-shell"
      style={style}
    >
      <div className="ai-sidebar-mention-card-stack">
        <div className="ai-sidebar-mention-card">
          <motion.div
            className="ai-sidebar-mention-card-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            {status === "ready" && items.length > 0 ? (
              <div
                ref={listRef}
                className="agent-mention-suggestions-list"
              >
                {items.map((item, index) => (
                  <button
                    key={`${item.kind}-${item.id}`}
                    type="button"
                    className="agent-mention-suggestion-item"
                    data-selected={index === selectedIndex}
                    onClick={() => onSelect(item, index)}
                    onMouseEnter={() => onSelectedIndexChange(index)}
                  >
                    <span
                      className="agent-mention-suggestion-icon"
                      aria-hidden="true"
                    >
                      {getItemIcon(item.kind)}
                    </span>
                    <span className="agent-mention-suggestion-copy">
                      <span className="agent-mention-suggestion-title">{item.title}</span>
                      <span className="agent-mention-suggestion-kind">{getItemMeta(item, t)}</span>
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="agent-mention-suggestion-state">{getStateMessage(status, t)}</div>
            )}
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
