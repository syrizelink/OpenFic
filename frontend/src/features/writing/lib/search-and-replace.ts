/**
 * Search and Replace Extension
 *
 * Ekstensi cari dan ganti untuk Tiptap
 * Berbasis implementasi sereneinserenade/tiptap-search-and-replace berlisensi MIT
 * https://github.com/sereneinserenade/tiptap-search-and-replace
 */

import { Extension, type Range } from "@tiptap/core";
import type { Node as PMNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, type EditorState, type Transaction } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

/** Tipe fungsi Dispatch */
type DispatchFn = ((tr: Transaction) => void) | undefined;

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    searchAndReplace: {
      /** Menyetel kata pencarian */
      setSearchTerm: (searchTerm: string) => ReturnType;
      /** Menyetel kata pengganti */
      setReplaceTerm: (replaceTerm: string) => ReturnType;
      /** Mereset indeks hasil saat ini menjadi 0 */
      resetIndex: () => ReturnType;
      /** Melompat ke hasil pencarian berikutnya */
      nextSearchResult: () => ReturnType;
      /** Melompat ke hasil pencarian sebelumnya */
      previousSearchResult: () => ReturnType;
      /** Mengganti kecocokan saat ini */
      replace: () => ReturnType;
      /** Mengganti seluruh kecocokan */
      replaceAll: () => ReturnType;
    };
  }
}

interface TextNodesWithPosition {
  text: string;
  pos: number;
}

/** Mengambil ekspresi reguler pencarian */
function getRegex(searchTerm: string): RegExp {
  // Meng-escape karakter khusus, tanpa membedakan huruf besar-kecil
  const escaped = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(escaped, "gui");
}

interface ProcessedSearches {
  decorationsToReturn: DecorationSet;
  results: Range[];
}

/** Menangani pencarian, menghasilkan dekorasi dan hasil */
function processSearches(
  doc: PMNode,
  searchTerm: RegExp,
  searchResultClass: string,
  resultIndex: number,
): ProcessedSearches {
  const decorations: Decoration[] = [];
  const results: Range[] = [];

  let textNodesWithPosition: TextNodesWithPosition[] = [];
  let index = 0;

  if (!searchTerm) {
    return {
      decorationsToReturn: DecorationSet.empty,
      results: [],
    };
  }

  // Mengumpulkan seluruh node teks beserta posisinya
  doc?.descendants((node, pos) => {
    if (node.isText) {
      if (textNodesWithPosition[index]) {
        textNodesWithPosition[index] = {
          text: textNodesWithPosition[index].text + node.text,
          pos: textNodesWithPosition[index].pos,
        };
      } else {
        textNodesWithPosition[index] = {
          text: `${node.text}`,
          pos,
        };
      }
    } else {
      index += 1;
    }
  });

  textNodesWithPosition = textNodesWithPosition.filter(Boolean);

  // Mencari seluruh kecocokan
  for (const element of textNodesWithPosition) {
    const { text, pos } = element;
    const matches = Array.from(text.matchAll(searchTerm)).filter(([matchText]) => matchText.trim());

    for (const m of matches) {
      if (m[0] === "") break;

      if (m.index !== undefined) {
        results.push({
          from: pos + m.index,
          to: pos + m.index + m[0].length,
        });
      }
    }
  }

  // Membuat dekorasi untuk setiap hasil
  for (let i = 0; i < results.length; i += 1) {
    const r = results[i];
    const className =
      i === resultIndex ? `${searchResultClass} ${searchResultClass}-current` : searchResultClass;
    const decoration: Decoration = Decoration.inline(r.from, r.to, {
      class: className,
    });

    decorations.push(decoration);
  }

  return {
    decorationsToReturn: DecorationSet.create(doc, decorations),
    results,
  };
}

/** Mengganti kecocokan pertama */
function replaceFirst(
  replaceTerm: string,
  results: Range[],
  resultIndex: number,
  { state, dispatch }: { state: EditorState; dispatch: DispatchFn },
) {
  const result = results[resultIndex];

  if (!result) return;

  const { from, to } = result;

  if (dispatch) dispatch(state.tr.insertText(replaceTerm, from, to));
}

/** Menghitung ulang pergeseran posisi hasil berikutnya */
function rebaseNextResult(
  replaceTerm: string,
  index: number,
  lastOffset: number,
  results: Range[],
): [number, Range[]] | null {
  const nextIndex = index + 1;

  if (!results[nextIndex]) return null;

  const { from: currentFrom, to: currentTo } = results[index];

  const offset = currentTo - currentFrom - replaceTerm.length + lastOffset;

  const { from, to } = results[nextIndex];

  results[nextIndex] = {
    to: to - offset,
    from: from - offset,
  };

  return [offset, results];
}

/** Mengganti seluruh kecocokan */
function replaceAllMatches(
  replaceTerm: string,
  results: Range[],
  { tr, dispatch }: { tr: Transaction; dispatch: DispatchFn },
) {
  let offset = 0;

  let resultsCopy = results.slice();

  if (!resultsCopy.length) return;

  for (let i = 0; i < resultsCopy.length; i += 1) {
    const { from, to } = resultsCopy[i];

    tr.insertText(replaceTerm, from, to);

    const rebaseNextResultResponse = rebaseNextResult(replaceTerm, i, offset, resultsCopy);

    if (!rebaseNextResultResponse) continue;

    offset = rebaseNextResultResponse[0];
    resultsCopy = rebaseNextResultResponse[1];
  }

  if (dispatch) dispatch(tr);
}

export const searchAndReplacePluginKey = new PluginKey("searchAndReplacePlugin");

export interface SearchAndReplaceOptions {
  /** Nama kelas CSS untuk hasil pencarian */
  searchResultClass: string;
}

export interface SearchAndReplaceStorage {
  searchTerm: string;
  replaceTerm: string;
  results: Range[];
  lastSearchTerm: string;
  resultIndex: number;
  lastResultIndex: number;
}

/** Mengambil storage searchAndReplace dari editor (dengan penegasan tipe) */
function getStorage(editor: any): SearchAndReplaceStorage {
  return editor.storage.searchAndReplace as SearchAndReplaceStorage;
}

export const SearchAndReplace = Extension.create<SearchAndReplaceOptions, SearchAndReplaceStorage>({
  name: "searchAndReplace",

  addOptions() {
    return {
      searchResultClass: "search-result",
    };
  },

  addStorage() {
    return {
      searchTerm: "",
      replaceTerm: "",
      results: [],
      lastSearchTerm: "",
      resultIndex: 0,
      lastResultIndex: 0,
    };
  },

  addCommands() {
    return {
      setSearchTerm:
        (searchTerm: string) =>
        ({ editor, dispatch, tr }) => {
          getStorage(editor).searchTerm = searchTerm;
          // Memicu penghitungan ulang plugin
          if (dispatch) {
            dispatch(tr.setMeta(searchAndReplacePluginKey, { updated: true }));
          }
          return true;
        },
      setReplaceTerm:
        (replaceTerm: string) =>
        ({ editor }) => {
          getStorage(editor).replaceTerm = replaceTerm;
          return false;
        },
      resetIndex:
        () =>
        ({ editor }) => {
          getStorage(editor).resultIndex = 0;
          return false;
        },
      nextSearchResult:
        () =>
        ({ editor, dispatch, tr }) => {
          const storage = getStorage(editor);
          const { results, resultIndex } = storage;

          const nextIndex = resultIndex + 1;

          if (results[nextIndex]) {
            storage.resultIndex = nextIndex;
          } else {
            storage.resultIndex = 0;
          }

          // Memakai setMeta untuk menandai transaksi agar plugin menghitung ulang
          if (dispatch) {
            dispatch(tr.setMeta(searchAndReplacePluginKey, { updated: true }));
          }

          return true;
        },
      previousSearchResult:
        () =>
        ({ editor, dispatch, tr }) => {
          const storage = getStorage(editor);
          const { results, resultIndex } = storage;

          const prevIndex = resultIndex - 1;

          if (results[prevIndex]) {
            storage.resultIndex = prevIndex;
          } else {
            storage.resultIndex = results.length - 1;
          }

          // Memakai setMeta untuk menandai transaksi agar plugin menghitung ulang
          if (dispatch) {
            dispatch(tr.setMeta(searchAndReplacePluginKey, { updated: true }));
          }

          return true;
        },
      replace:
        () =>
        ({ editor, state, dispatch }) => {
          const { replaceTerm, results, resultIndex } = getStorage(editor);

          replaceFirst(replaceTerm, results, resultIndex, { state, dispatch });

          return false;
        },
      replaceAll:
        () =>
        ({ editor, tr, dispatch }) => {
          const { replaceTerm, results } = getStorage(editor);

          replaceAllMatches(replaceTerm, results, { tr, dispatch });

          return false;
        },
    };
  },

  addProseMirrorPlugins() {
    const editor = this.editor;
    const { searchResultClass } = this.options;

    const setLastSearchTerm = (t: string) => (getStorage(editor).lastSearchTerm = t);
    const setLastResultIndex = (t: number) => (getStorage(editor).lastResultIndex = t);

    return [
      new Plugin({
        key: searchAndReplacePluginKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, oldState) {
            const { doc, docChanged } = tr;
            const storage = getStorage(editor);
            const { searchTerm, lastSearchTerm, resultIndex, lastResultIndex } = storage;

            // Memeriksa adanya sinyal pembaruan dari setMeta
            const metaUpdate = tr.getMeta(searchAndReplacePluginKey);

            if (
              !docChanged &&
              !metaUpdate &&
              lastSearchTerm === searchTerm &&
              lastResultIndex === resultIndex
            )
              return oldState;

            setLastSearchTerm(searchTerm);
            setLastResultIndex(resultIndex);

            if (!searchTerm) {
              storage.results = [];
              return DecorationSet.empty;
            }

            const { decorationsToReturn, results } = processSearches(
              doc,
              getRegex(searchTerm),
              searchResultClass,
              resultIndex,
            );

            storage.results = results;

            return decorationsToReturn;
          },
        },
        props: {
          decorations(state) {
            return this.getState(state);
          },
        },
      }),
    ];
  },
});

export default SearchAndReplace;
