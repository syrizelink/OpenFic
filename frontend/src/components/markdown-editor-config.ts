import { Extension, type JSONContent } from "@tiptap/core";
import CharacterCount from "@tiptap/extension-character-count";
import { CodeBlockLowlight } from "@tiptap/extension-code-block-lowlight";
import { OrderedList, TaskList, TaskItem } from "@tiptap/extension-list";
import Placeholder from "@tiptap/extension-placeholder";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "@tiptap/markdown";
import { Plugin } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";
import { createLowlight, common } from "lowlight";

import { serializeClipboardMarkdown } from "./editor-clipboard";
import { createEditorShortcuts, type EditorShortcutCallbacks } from "./editor-shortcuts";

export type { EditorShortcutCallbacks } from "./editor-shortcuts";

const MarkdownOrderedList = OrderedList.extend({
  parseMarkdown(token, helpers) {
    const parsed = OrderedList.config.parseMarkdown!(token, helpers);
    if (Array.isArray(parsed)) return parsed;

    return {
      ...parsed,
      // Empty items need a paragraph to satisfy the listItem schema. Otherwise
      // they are discarded when the saved Markdown is loaded back into Tiptap.
      content: parsed.content?.map((item) => ({
        ...item,
        content:
          item.content?.[0]?.type === "paragraph"
            ? item.content
            : [{ type: "paragraph" }, ...(item.content ?? [])],
      })),
    };
  },
});

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

function unwrapSingleParagraph(content: JSONContent[]): JSONContent[] | null {
  if (content.length !== 1) {
    return null;
  }
  const node = content[0];
  if (node.type !== "paragraph" || !node.content?.length) {
    return null;
  }
  return node.content;
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
            const parsed = normalizeMarkExclusions(json.content);
            const content = unwrapSingleParagraph(parsed) ?? parsed;
            editor.commands.insertContent(content);
            return true;
          },
          clipboardTextSerializer(slice) {
            if (!editor.markdown) {
              return "";
            }
            const content = slice.content.toJSON() as JSONContent[];
            return serializeClipboardMarkdown(editor.markdown, { type: "doc", content });
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
      orderedList: false,
      link: {
        openOnClick: false,
      },
    }),
    MarkdownOrderedList,
    TableKit,
    TaskList,
    TaskItem.configure({ nested: true }),
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
