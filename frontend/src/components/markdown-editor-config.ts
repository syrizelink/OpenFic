import { Extension, type JSONContent } from "@tiptap/core";
import CharacterCount from "@tiptap/extension-character-count";
import { CodeBlockLowlight } from "@tiptap/extension-code-block-lowlight";
import { TaskList, TaskItem } from "@tiptap/extension-list";
import Placeholder from "@tiptap/extension-placeholder";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "@tiptap/markdown";
import { Plugin } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";
import { createLowlight, common } from "lowlight";

import { createEditorShortcuts, type EditorShortcutCallbacks } from "./editor-shortcuts";

export type { EditorShortcutCallbacks } from "./editor-shortcuts";

function normalizeMarkExclusions(content: JSONContent | JSONContent[]): JSONContent[] {
  const nodes = Array.isArray(content) ? content : [content];
  return nodes.map((node) => {
    if (node.content) {
      return { ...node, content: normalizeMarkExclusions(node.content) };
    }
    const marks = node.marks as unknown as { type: string }[] | undefined;
    if (!marks?.some((m) => m.type === "code")) {
      return node;
    }
    return { ...node, marks: [{ type: "code" }] };
  });
}

const MarkdownClipboard = Extension.create({
  name: "markdownClipboard",
  priority: 1000,

  addProseMirrorPlugins() {
    const editor = this.editor;

    return [
      new Plugin({
        props: {
          handlePaste(view, event) {
            const data = event.clipboardData;
            if (!data) {
              return false;
            }

            const { selection } = view.state;
            const $pos = selection.$from;
            for (let depth = $pos.depth; depth > 0; depth -= 1) {
              if ($pos.node(depth).type.name === "codeBlock") {
                return false;
              }
            }
            const activeMarks = selection.$from.marks();
            if (activeMarks.some((m) => m.type.name === "code")) {
              return false;
            }

            let text = data.getData("text/plain");
            if (!text) {
              const html = data.getData("text/html");
              if (!html) {
                return false;
              }
              const doc = new DOMParser().parseFromString(html, "text/html");
              text = doc.body.textContent ?? "";
            }

            if (!text || !editor.markdown) {
              return false;
            }

            const json = editor.markdown.parse(text);
            if (!json.content?.length) {
              return false;
            }
            editor.commands.insertContent(normalizeMarkExclusions(json.content));
            return true;
          },
          clipboardTextSerializer(slice) {
            if (!editor.markdown) {
              return "";
            }
            const content = slice.content.toJSON() as JSONContent[];
            return editor.markdown.serialize({ type: "doc", content });
          },
        },
      }),
    ];
  },
});

export interface MarkdownEditorExtensionsOptions {
  placeholder?: string;
  shortcuts?: EditorShortcutCallbacks;
}

export function createMarkdownEditorExtensions(options: MarkdownEditorExtensionsOptions = {}) {
  const { placeholder = "", shortcuts } = options;

  const extensions = [
    StarterKit.configure({
      codeBlock: false,
    }),
    TableKit,
    TaskList,
    TaskItem,
    CodeBlockLowlight.configure({
      lowlight: createLowlight(common),
    }),
    Placeholder.configure({
      placeholder,
    }),
    CharacterCount,
    Markdown,
    MarkdownClipboard,
  ];

  if (shortcuts) {
    extensions.push(createEditorShortcuts(shortcuts));
  }

  return extensions;
}
