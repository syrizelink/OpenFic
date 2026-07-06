/**
 * MacroNode Extension - Tiptap 宏节点扩展
 *
 * 将宏表达式渲染为可交互的标签。
 */

import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";

import { MacroNodeView } from "./macro-node-view";

export interface MacroNodeAttributes {
  macroName: string;
  macroRaw: string;
  macroData: string;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    macroNode: {
      insertMacro: (attrs: MacroNodeAttributes) => ReturnType;
    };
  }
}

export const MacroNode = Node.create({
  name: "macroNode",

  group: "inline",

  inline: true,

  atom: true,

  selectable: true,

  draggable: false,

  addAttributes() {
    return {
      macroName: {
        default: "",
      },
      macroRaw: {
        default: "",
      },
      macroData: {
        default: "{}",
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-macro-node="true"]',
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-macro-node": "true",
        class: `macro-node macro-${HTMLAttributes.macroName || "unknown"}`,
      }),
      HTMLAttributes.macroRaw || "",
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(MacroNodeView);
  },

  addCommands() {
    return {
      insertMacro:
        (attrs) =>
        ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs,
          });
        },
    };
  },
});
