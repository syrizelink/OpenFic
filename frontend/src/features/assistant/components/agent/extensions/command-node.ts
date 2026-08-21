import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";

import { CommandNodeView } from "./command-node-view";

export interface AssistantCommandNodeAttributes {
  commandKind: string;
  commandLabel: string;
  commandRaw: string;
  commandId: string;
  commandName: string;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    assistantCommand: {
      insertAssistantCommand: (attrs: AssistantCommandNodeAttributes) => ReturnType;
    };
  }
}

export const CommandNode = Node.create({
  name: "assistantCommand",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      commandKind: { default: "" },
      commandLabel: { default: "" },
      commandRaw: { default: "" },
      commandId: { default: "" },
      commandName: { default: "" },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-assistant-command="true"]',
        getAttrs: (node) => {
          if (!(node instanceof HTMLElement)) return false;
          return {
            commandKind: node.dataset.commandKind ?? "",
            commandLabel: node.dataset.commandLabel ?? "",
            commandRaw: node.dataset.commandRaw ?? "",
            commandId: node.dataset.commandId ?? "",
            commandName: node.dataset.commandName ?? "",
          };
        },
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-assistant-command": "true",
        "data-command-kind": HTMLAttributes.commandKind || "",
        "data-command-label": HTMLAttributes.commandLabel || "",
        "data-command-raw": HTMLAttributes.commandRaw || "",
        "data-command-id": HTMLAttributes.commandId || "",
        "data-command-name": HTMLAttributes.commandName || "",
      }),
      HTMLAttributes.commandLabel || "",
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(CommandNodeView);
  },

  addCommands() {
    return {
      insertAssistantCommand:
        (attrs: AssistantCommandNodeAttributes) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs,
          }),
    };
  },
});
