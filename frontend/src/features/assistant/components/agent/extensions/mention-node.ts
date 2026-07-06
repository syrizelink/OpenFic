import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";

import { MentionNodeView } from "./mention-node-view";

export interface AssistantMentionNodeAttributes {
  mentionKind: string;
  mentionLabel: string;
  mentionRaw: string;
  mentionBody: string;
  volumeId: string;
  chapterId: string;
  noteId: string;
  noteCategoryId: string;
  startLine: string;
  endLine: string;
}

export interface AssistantMentionNodeOptions {
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    assistantMention: {
      insertAssistantMention: (attrs: AssistantMentionNodeAttributes) => ReturnType;
    };
  }
}

export const MentionNode = Node.create<AssistantMentionNodeOptions>({
  name: "assistantMention",
  addOptions() {
    return {
      onOpenMentionChapter: undefined,
    };
  },
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      mentionKind: { default: "" },
      mentionLabel: { default: "" },
      mentionRaw: { default: "" },
      mentionBody: { default: "" },
      volumeId: { default: "" },
      chapterId: { default: "" },
      noteId: { default: "" },
      noteCategoryId: { default: "" },
      startLine: { default: "" },
      endLine: { default: "" },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-assistant-mention="true"]',
        getAttrs: (node) => {
          if (!(node instanceof HTMLElement)) return false;
          return {
            mentionKind: node.dataset.mentionKind ?? "",
            mentionLabel: node.dataset.mentionLabel ?? "",
            mentionRaw: node.dataset.mentionRaw ?? "",
            mentionBody: node.dataset.mentionBody ?? "",
            volumeId: node.dataset.mentionVolumeId ?? "",
            chapterId: node.dataset.mentionChapterId ?? "",
            noteId: node.dataset.mentionNoteId ?? "",
            noteCategoryId: node.dataset.mentionNoteCategoryId ?? "",
            startLine: node.dataset.mentionStartLine ?? "",
            endLine: node.dataset.mentionEndLine ?? "",
          };
        },
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-assistant-mention": "true",
        "data-mention-kind": HTMLAttributes.mentionKind || "",
        "data-mention-label": HTMLAttributes.mentionLabel || "",
        "data-mention-raw": HTMLAttributes.mentionRaw || "",
        "data-mention-body": HTMLAttributes.mentionBody || "",
        "data-mention-volume-id": HTMLAttributes.volumeId || "",
        "data-mention-chapter-id": HTMLAttributes.chapterId || "",
        "data-mention-note-id": HTMLAttributes.noteId || "",
        "data-mention-note-category-id": HTMLAttributes.noteCategoryId || "",
        "data-mention-start-line": HTMLAttributes.startLine || "",
        "data-mention-end-line": HTMLAttributes.endLine || "",
      }),
      HTMLAttributes.mentionLabel || "",
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(MentionNodeView);
  },

  addCommands() {
    return {
      insertAssistantMention:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs,
          }),
    };
  },
});
