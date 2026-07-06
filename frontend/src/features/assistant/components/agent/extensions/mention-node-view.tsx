import { NodeViewWrapper, type NodeViewProps } from "@tiptap/react";

import {
  getMentionNavigationTarget,
  type AssistantMentionKind,
  type AssistantMentionToken,
} from "@/features/assistant/lib/mention-text";

import { MentionChip } from "../mention-chip";

export function MentionNodeView({ node, selected, extension }: NodeViewProps) {
  const kind = (node.attrs.mentionKind ?? "chapter") as AssistantMentionKind;
  const label = (node.attrs.mentionLabel ?? node.attrs.mentionRaw ?? kind) as string;
  const token: AssistantMentionToken = {
    raw: String(node.attrs.mentionRaw ?? ""),
    kind,
    attrs: {
      kind,
      label: String(node.attrs.mentionLabel ?? ""),
      volume_id: String(node.attrs.volumeId ?? ""),
      chapter_id: String(node.attrs.chapterId ?? ""),
      note_id: String(node.attrs.noteId ?? ""),
      note_category_id: String(node.attrs.noteCategoryId ?? ""),
      start_line: String(node.attrs.startLine ?? ""),
      end_line: String(node.attrs.endLine ?? ""),
    },
    body: String(node.attrs.mentionBody ?? ""),
  };
  const navigationTarget = getMentionNavigationTarget(token);
  const handleOpenMentionChapter = navigationTarget?.chapterId
    ? (extension.options.onOpenMentionChapter as
        | ((chapterId: string, chapterTitle: string) => void)
        | undefined)
    : undefined;

  return (
    <NodeViewWrapper
      as="span"
      data-mention-kind={kind}
      draggable={false}
    >
      <MentionChip
        kind={kind}
        label={label}
        selected={selected}
        onClick={
          navigationTarget?.chapterId && handleOpenMentionChapter
            ? () => {
                handleOpenMentionChapter(navigationTarget.chapterId!, navigationTarget.title);
              }
            : undefined
        }
      />
    </NodeViewWrapper>
  );
}
