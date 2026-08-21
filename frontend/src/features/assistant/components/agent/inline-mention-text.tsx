import { forwardRef } from "react";

import { getCommandDisplayLabel } from "@/features/assistant/lib/command-text";
import {
  getMentionNavigationTarget,
  getMentionDisplayLabel,
  parseAssistantMarkup,
} from "@/features/assistant/lib/mention-text";

import { MentionChip } from "./mention-chip";

interface InlineMentionTextProps {
  text: string;
  className?: string;
  singleLine?: boolean;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
}

export const InlineMentionText = forwardRef<HTMLSpanElement, InlineMentionTextProps>(
  function InlineMentionText({ text, className, singleLine = false, onOpenMentionChapter }, ref) {
    const segments = parseAssistantMarkup(text);
    const classes = [
      "agent-inline-mention-text",
      singleLine ? "agent-inline-mention-text--single-line" : "",
      className ?? "",
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <span
        ref={ref}
        className={classes}
      >
        {segments.map((segment, index) =>
          typeof segment === "string" ? (
            <span key={`text-${index}`}>{segment}</span>
          ) : segment.markup === "command" ? (
            <MentionChip
              key={`command-${index}-${segment.raw}`}
              kind={segment.kind}
              label={getCommandDisplayLabel(segment)}
            />
          ) : (
            <MentionChip
              key={`mention-${index}-${segment.raw}`}
              kind={segment.kind}
              label={getMentionDisplayLabel(segment)}
              onClick={(() => {
                const navigationTarget = getMentionNavigationTarget(segment);
                if (!navigationTarget || !onOpenMentionChapter) return undefined;
                if (!navigationTarget.chapterId) return undefined;
                return () => {
                  onOpenMentionChapter(navigationTarget.chapterId!, navigationTarget.title);
                };
              })()}
            />
          ),
        )}
      </span>
    );
  },
);
