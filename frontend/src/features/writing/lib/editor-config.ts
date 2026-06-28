/**
 * Editor Configuration
 *
 * Tiptap 编辑器扩展配置 - 纯文本模式。
 */

import { Extension } from "@tiptap/react";
import Document from "@tiptap/extension-document";
import Paragraph from "@tiptap/extension-paragraph";
import Text from "@tiptap/extension-text";
import History from "@tiptap/extension-history";
import Placeholder from "@tiptap/extension-placeholder";
import CharacterCount from "@tiptap/extension-character-count";

import { SearchAndReplace } from "./search-and-replace";
import {
  createEditorShortcuts,
  type EditorShortcutCallbacks,
} from "@/components/editor-shortcuts";

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
    SearchAndReplace,
  ];

  // 如果提供了快捷键回调，添加快捷键扩展
  if (shortcuts) {
    extensions.push(createEditorShortcuts(shortcuts));
  }

  return extensions;
}
