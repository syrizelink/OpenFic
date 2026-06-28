/**
 * MacroInputRule - 宏输入规则
 *
 * 检测 }} 输入时回溯查找 {{ 并解析宏。
 */

import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { findMacros, tryParseMacro } from "@/lib/macro";
import type { MacroNodeAttributes } from "./macro-node";

export const MacroInputRule = Extension.create({
  name: "macroInputRule",

  addProseMirrorPlugins() {
    const editor = this.editor;

    return [
      new Plugin({
        key: new PluginKey("macroInputRule"),

        appendTransaction(transactions, _oldState, newState) {
          const docChanged = transactions.some((tr) => tr.docChanged);
          if (!docChanged) return null;

          const { selection } = newState;
          const { $from } = selection;

          const textBefore = $from.parent.textBetween(
            0,
            $from.parentOffset,
            undefined,
            "\ufffc"
          );

          if (!textBefore.endsWith("}}")) return null;

          const matches = findMacros(textBefore);
          if (matches.length === 0) return null;

          const lastMatch = matches[matches.length - 1];
          if (lastMatch.end !== textBefore.length) return null;

          const macroNode = tryParseMacro(lastMatch);
          if (!macroNode) return null;

          const tr = newState.tr;

          const startPos = $from.start() + lastMatch.start;
          const endPos = $from.start() + lastMatch.end;

          const attrs: MacroNodeAttributes = {
            macroName: macroNode.name,
            macroRaw: macroNode.raw,
            macroData: JSON.stringify({ args: macroNode.args }),
          };

          const node = editor.schema.nodes.macroNode.create(attrs);

          tr.replaceWith(startPos, endPos, node);

          return tr;
        },
      }),
    ];
  },
});
