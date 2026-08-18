/**
 * Editor Configuration
 *
 * Tiptap 编辑器扩展配置 - 纯文本模式。
 */

import type { JSONContent } from "@tiptap/core";
import CharacterCount from "@tiptap/extension-character-count";
import Document from "@tiptap/extension-document";
import History from "@tiptap/extension-history";
import Paragraph from "@tiptap/extension-paragraph";
import Placeholder from "@tiptap/extension-placeholder";
import Text from "@tiptap/extension-text";
import { Plugin } from "@tiptap/pm/state";
import { Extension } from "@tiptap/react";

import { serializeClipboardText } from "@/components/editor-clipboard";
import { createEditorShortcuts, type EditorShortcutCallbacks } from "@/components/editor-shortcuts";

import { SearchAndReplace } from "./search-and-replace";

export type { EditorShortcutCallbacks } from "@/components/editor-shortcuts";

const PARAGRAPH_INDENT = "\u3000\u3000";

const HALFWIDTH_PUNCTUATION_MAP: Record<string, string> = {
  ",": "，",
  ".": "。",
  "?": "？",
  "!": "！",
  ":": "：",
  ";": "；",
  "(": "（",
  ")": "）",
};

function countOccurrences(text: string, target: string): number {
  let count = 0;
  let index = text.indexOf(target);
  while (index !== -1) {
    count += 1;
    index = text.indexOf(target, index + 1);
  }
  return count;
}

function convertHalfwidthPunctuation(text: string, precedingText: string): string {
  let result = "";
  let context = precedingText;

  for (const char of text) {
    if (char === '"') {
      const open = countOccurrences(context, "“");
      const close = countOccurrences(context, "”");
      const converted = open > close ? "”" : "“";
      result += converted;
      context += converted;
    } else if (char === "'") {
      const open = countOccurrences(context, "‘");
      const close = countOccurrences(context, "’");
      const converted = open > close ? "’" : "‘";
      result += converted;
      context += converted;
    } else {
      const converted = HALFWIDTH_PUNCTUATION_MAP[char] ?? char;
      result += converted;
      context += converted;
    }
  }

  return result;
}

const TabIndent = Extension.create({
  name: "tabIndent",

  addKeyboardShortcuts() {
    return {
      Tab: ({ editor }) => {
        editor.commands.insertContent(PARAGRAPH_INDENT);
        return true;
      },
    };
  },
});

function createParagraphAutoIndent(shouldAutoIndent: () => boolean) {
  return Extension.create({
    name: "paragraphAutoIndent",

    addKeyboardShortcuts() {
      return {
        Enter: ({ editor }) => {
          if (!shouldAutoIndent()) {
            return false;
          }

          const { $from } = editor.state.selection;
          if (!$from.parent.isTextblock) {
            return false;
          }
          if (!$from.parent.textContent.startsWith(PARAGRAPH_INDENT)) {
            return false;
          }

          editor.chain().splitBlock().insertContent(PARAGRAPH_INDENT).run();
          return true;
        },
      };
    },
  });
}

function createAutoConvertPunctuation(shouldConvert: () => boolean) {
  return Extension.create({
    name: "autoConvertPunctuation",

    addProseMirrorPlugins() {
      return [
        new Plugin({
          props: {
            handleTextInput(view, from, to, text) {
              if (!shouldConvert()) {
                return false;
              }

              const precedingText = view.state.doc.textBetween(0, from);
              const converted = convertHalfwidthPunctuation(text, precedingText);
              if (converted === text) {
                return false;
              }

              view.dispatch(view.state.tr.replaceWith(from, to, view.state.schema.text(converted)));
              return true;
            },
          },
        }),
      ];
    },
  });
}

const PlainTextClipboard = Extension.create({
  name: "plainTextClipboard",

  addProseMirrorPlugins() {
    const editor = this.editor;

    return [
      new Plugin({
        props: {
          handlePaste(_view, event) {
            const text = event.clipboardData?.getData("text/plain");
            if (!text) {
              return false;
            }

            editor.commands.insertContent(createPlainTextPasteContent(text));
            return true;
          },
          clipboardTextSerializer(slice) {
            return serializeClipboardText(slice.content, editor.schema);
          },
        },
      }),
    ];
  },
});

export function createPlainTextPasteContent(text: string): JSONContent[] {
  const normalized = text.replace(/\r\n?/g, "\n");
  const lines = normalized.split("\n");

  if (lines.length === 1) {
    return [{ type: "text", text: lines[0] ?? "" }];
  }

  return lines.map((line) => {
    if (!line) {
      return { type: "paragraph" };
    }
    return { type: "paragraph", content: [{ type: "text", text: line }] };
  });
}

/**
 * 编辑器扩展配置选项
 */
export interface EditorExtensionsOptions {
  /** 占位符文本 */
  placeholder?: string;
  /** 编辑器快捷键回调 */
  shortcuts?: EditorShortcutCallbacks;
  /** 换行时是否继承当前段落的段首两格缩进 */
  autoIndent?: () => boolean;
  /** 输入时是否将半角标点符号转换为全角 */
  autoConvertPunctuation?: () => boolean;
}

/**
 * 纯文本编辑器扩展配置
 *
 * 只包含基础的段落编辑功能，不支持任何富文本格式：
 * - Document: 文档根节点
 * - Paragraph: 段落
 * - Text: 文本
 * - History: 撤销/重做
 * - Placeholder: 占位符文本
 * - CharacterCount: 字符计数（实时更新）
 * - TabIndent: Tab 键缩进（2em）
 * - SearchAndReplace: 查找和替换
 * - EditorShortcuts: 编辑器快捷键（Mod-f, Mod-h, Mod-s）
 */
export function createEditorExtensions(options: EditorExtensionsOptions = {}) {
  const { placeholder = "开始写作...", shortcuts, autoIndent, autoConvertPunctuation } = options;

  const extensions = [
    Document,
    Paragraph,
    Text,
    History,
    Placeholder.configure({
      placeholder,
    }),
    CharacterCount,
    TabIndent,
    PlainTextClipboard,
    SearchAndReplace,
  ];

  // 如果提供了快捷键回调，添加快捷键扩展
  if (shortcuts) {
    extensions.push(createEditorShortcuts(shortcuts));
  }

  // 如果启用了段落自动缩进，添加换行继承扩展
  if (autoIndent) {
    extensions.push(createParagraphAutoIndent(autoIndent));
  }

  // 如果启用了半角标点自动转换，添加输入转换扩展
  if (autoConvertPunctuation) {
    extensions.push(createAutoConvertPunctuation(autoConvertPunctuation));
  }

  return extensions;
}
