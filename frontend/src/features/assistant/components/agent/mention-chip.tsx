import { BookOpen, FileText, Folder, Quote, StickyNote } from "lucide-react";
import type { ReactNode } from "react";

import type { AssistantMentionKind } from "@/features/assistant/lib/mention-text";

import "./agent-mentions.css";

function getMentionIcon(kind: AssistantMentionKind): ReactNode {
  if (kind === "volume") return <BookOpen size={12} />;
  if (kind === "chapter") return <FileText size={12} />;
  if (kind === "note") return <StickyNote size={12} />;
  if (kind === "note_category") return <Folder size={12} />;
  return <Quote size={12} />;
}

export function MentionChip({
  kind,
  label,
  selected = false,
  onClick,
}: {
  kind: AssistantMentionKind;
  label: string;
  selected?: boolean;
  onClick?: () => void;
}) {
  const content = (
    <>
      <span
        className="agent-mention-chip-icon"
        aria-hidden="true"
      >
        {getMentionIcon(kind)}
      </span>
      <span className="agent-mention-chip-label">{label}</span>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className="agent-mention-chip"
        data-kind={kind}
        data-selected={selected}
        data-clickable="true"
        draggable={false}
        onDragStart={(event) => {
          event.preventDefault();
        }}
        onClick={(event) => {
          event.stopPropagation();
          onClick();
        }}
      >
        {content}
      </button>
    );
  }

  return (
    <span
      className="agent-mention-chip"
      data-kind={kind}
      data-selected={selected}
      draggable={false}
      onDragStart={(event) => {
        event.preventDefault();
      }}
    >
      {content}
    </span>
  );
}
