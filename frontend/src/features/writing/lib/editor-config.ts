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

const TabIndent = Extension.create({
  name: "tabIndent",

  addKeyboardShortcuts() {
    return {
      Tab: ({ editor }) => {
        editor.commands.insertContent("\u3000\u3000");
        return true;
      },
    };
  },
});

const PlainTextClipboard = Extension.create({
  name: "plainTextClipboard",

  addProseMirrorPlugins() {
    const editor = this.editor;

    return [
      new Plugin({
        props: {
          handlePaste(_view, event) {
            const text = event.clipboardData?.getData("text/plain");
            if (text === undefined) {
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
  return text
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => {
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
  const { placeholder = "开始写作...", shortcuts } = options;

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

  return extensions;
}
