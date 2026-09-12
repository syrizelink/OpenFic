/**
 * Editor Configuration
 *
 * Konfigurasi ekstensi editor Tiptap - mode teks polos.
 */

import type { JSONContent } from "@tiptap/core";
import CharacterCount from "@tiptap/extension-character-count";
import Document from "@tiptap/extension-document";
import History from "@tiptap/extension-history";
import Paragraph from "@tiptap/extension-paragraph";
import Placeholder from "@tiptap/extension-placeholder";
import Text from "@tiptap/extension-text";
import { Plugin, TextSelection, type Transaction } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import { Extension } from "@tiptap/react";

import { serializeClipboardText } from "@/components/editor-clipboard";
import { createEditorShortcuts, type EditorShortcutCallbacks } from "@/components/editor-shortcuts";
import { PARAGRAPH_INDENT } from "@/components/editor-toolbar-actions";
import i18n from "@/i18n";

import { SearchAndReplace } from "./search-and-replace";

export type { EditorShortcutCallbacks } from "@/components/editor-shortcuts";

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

export interface AutoPairSymbol {
  open: string;
  close: string;
}

const AUTO_PAIR_SYMBOLS: AutoPairSymbol[] = [
  { open: "(", close: ")" },
  { open: "[", close: "]" },
  { open: "{", close: "}" },
  { open: '"', close: '"' },
  { open: "'", close: "'" },
  { open: "（", close: "）" },
  { open: "【", close: "】" },
  { open: "「", close: "」" },
  { open: "『", close: "』" },
  { open: "《", close: "》" },
  { open: "“", close: "”" },
  { open: "‘", close: "’" },
];

const CONVERTED_AUTO_PAIR_SYMBOLS: Record<string, AutoPairSymbol> = {
  "(": { open: "（", close: "）" },
  '"': { open: "“", close: "”" },
  "'": { open: "‘", close: "’" },
};

export function resolveAutoPairSymbol(
  input: string,
  shouldConvertPunctuation: boolean,
): AutoPairSymbol | null {
  const pair = AUTO_PAIR_SYMBOLS.find((candidate) => candidate.open === input);
  if (!pair) return null;

  if (shouldConvertPunctuation) {
    return CONVERTED_AUTO_PAIR_SYMBOLS[input] ?? pair;
  }

  return pair;
}

function resolveAutoPairClosingSymbol(
  input: string,
  shouldConvertPunctuation: boolean,
): string | null {
  const pair = AUTO_PAIR_SYMBOLS.find((candidate) => candidate.close === input);
  if (!pair) return null;

  if (shouldConvertPunctuation) {
    const convertedPair = CONVERTED_AUTO_PAIR_SYMBOLS[pair.open];
    return convertedPair?.close ?? pair.close;
  }

  return pair.close;
}

export function getEmptyPairAtCursor(textBefore: string, textAfter: string): AutoPairSymbol | null {
  const open = Array.from(textBefore).at(-1);
  const close = Array.from(textAfter)[0];
  if (!open || !close) return null;

  return AUTO_PAIR_SYMBOLS.find((pair) => pair.open === open && pair.close === close) ?? null;
}

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

function isCompositionTextInput(
  view: Pick<EditorView, "composing">,
  defaultTransaction: () => Transaction,
): boolean {
  return view.composing || defaultTransaction().getMeta("composition") !== undefined;
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
            handleTextInput(view, from, to, text, defaultTransaction) {
              if (!shouldConvert() || isCompositionTextInput(view, defaultTransaction)) {
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

function createAutoPairSymbols(shouldPair: () => boolean, shouldConvertPunctuation: () => boolean) {
  return Extension.create({
    name: "autoPairSymbols",

    addProseMirrorPlugins() {
      return [
        new Plugin({
          props: {
            handleTextInput(view, from, to, text, defaultTransaction) {
              if (
                !shouldPair() ||
                from !== to ||
                Array.from(text).length !== 1 ||
                isCompositionTextInput(view, defaultTransaction)
              ) {
                return false;
              }

              const convertPunctuation = shouldConvertPunctuation();
              const closingSymbol = resolveAutoPairClosingSymbol(text, convertPunctuation);
              const textAfter = view.state.doc.textBetween(
                from,
                Math.min(from + 1, view.state.doc.content.size),
              );
              if (closingSymbol && textAfter === closingSymbol) {
                view.dispatch(
                  view.state.tr.setSelection(
                    TextSelection.create(view.state.doc, from + closingSymbol.length),
                  ),
                );
                return true;
              }

              const pair = resolveAutoPairSymbol(text, convertPunctuation);
              if (!pair) return false;

              const transaction = view.state.tr.replaceWith(
                from,
                to,
                view.state.schema.text(`${pair.open}${pair.close}`),
              );
              transaction.setSelection(
                TextSelection.create(transaction.doc, from + pair.open.length),
              );
              view.dispatch(transaction);
              return true;
            },
            handleKeyDown(view, event) {
              if (!shouldPair() || event.key !== "Backspace") return false;
              if (event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return false;

              const { selection } = view.state;
              if (!selection.empty) return false;

              const textBefore = view.state.doc.textBetween(0, selection.from);
              const textAfter = view.state.doc.textBetween(
                selection.from,
                view.state.doc.content.size,
              );
              const pair = getEmptyPairAtCursor(textBefore, textAfter);
              if (!pair) return false;

              view.dispatch(
                view.state.tr.delete(
                  selection.from - pair.open.length,
                  selection.from + pair.close.length,
                ),
              );
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
 * Opsi konfigurasi ekstensi editor
 */
export interface EditorExtensionsOptions {
  /** Teks pengisi sementara */
  placeholder?: string;
  /** Callback pintasan papan tombol editor */
  shortcuts?: EditorShortcutCallbacks;
  /** Menentukan apakah baris baru mewarisi indentasi dua spasi di awal paragraf saat ini */
  autoIndent?: () => boolean;
  /** Menentukan apakah tanda baca setengah lebar diubah menjadi lebar penuh saat diketik */
  autoConvertPunctuation?: () => boolean;
  /** Menentukan apakah simbol penutup dilengkapi otomatis saat simbol pembuka pasangan diketik */
  autoPairSymbols?: () => boolean;
}

/**
 * Konfigurasi ekstensi editor teks polos
 *
 * Hanya memuat fungsi penyuntingan paragraf dasar, tanpa dukungan format teks kaya apa pun:
 * - Document: node akar dokumen
 * - Paragraph: paragraf
 * - Text: teks
 * - History: batalkan/ulangi
 * - Placeholder: teks pengisi sementara
 * - CharacterCount: penghitung karakter (diperbarui langsung)
 * - TabIndent: indentasi tombol Tab (2em)
 * - SearchAndReplace: cari dan ganti
 * - EditorShortcuts: pintasan papan tombol editor (Mod-f, Mod-h, Mod-s)
 */
export function createEditorExtensions(options: EditorExtensionsOptions = {}) {
  const {
    placeholder = i18n.t("writing.contentPlaceholder"),
    shortcuts,
    autoIndent,
    autoConvertPunctuation,
    autoPairSymbols,
  } = options;

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

  // Jika callback pintasan disediakan, tambahkan ekstensi pintasan
  if (shortcuts) {
    extensions.push(createEditorShortcuts(shortcuts));
  }

  // Jika indentasi paragraf otomatis diaktifkan, tambahkan ekstensi pewarisan baris baru
  if (autoIndent) {
    extensions.push(createParagraphAutoIndent(autoIndent));
  }

  // Jika konversi otomatis tanda baca setengah lebar diaktifkan, tambahkan ekstensi konversi masukan
  if (autoConvertPunctuation) {
    extensions.push(createAutoConvertPunctuation(autoConvertPunctuation));
  }

  // Tiptap membalik urutan ekstensi saat mendaftarkan plugin ProseMirror, jadi ekstensi pelengkap harus ditambahkan paling akhir.
  if (autoPairSymbols) {
    extensions.push(
      createAutoPairSymbols(autoPairSymbols, autoConvertPunctuation ?? (() => false)),
    );
  }

  return extensions;
}
