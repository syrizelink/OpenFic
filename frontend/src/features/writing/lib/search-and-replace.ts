/**
 * Search and Replace Extension
 *
 * Tiptap 查找和替换扩展
 * 基于 MIT 许可的 sereneinserenade/tiptap-search-and-replace 实现
 * https://github.com/sereneinserenade/tiptap-search-and-replace
 */

import { Extension, type Range } from "@tiptap/core";
import type { Node as PMNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, type EditorState, type Transaction } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

/** Dispatch 函数类型 */
type DispatchFn = ((tr: Transaction) => void) | undefined;

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    searchAndReplace: {
      /** 设置搜索词 */
      setSearchTerm: (searchTerm: string) => ReturnType;
      /** 设置替换词 */
      setReplaceTerm: (replaceTerm: string) => ReturnType;
      /** 重置当前结果索引为 0 */
      resetIndex: () => ReturnType;
      /** 跳转到下一个搜索结果 */
      nextSearchResult: () => ReturnType;
      /** 跳转到上一个搜索结果 */
      previousSearchResult: () => ReturnType;
      /** 替换当前匹配项 */
      replace: () => ReturnType;
      /** 替换所有匹配项 */
      replaceAll: () => ReturnType;
    };
  }
}

interface TextNodesWithPosition {
  text: string;
  pos: number;
}

/** 获取搜索正则表达式 */
function getRegex(searchTerm: string): RegExp {
  // 转义特殊字符，不区分大小写
  const escaped = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(escaped, "gui");
}

interface ProcessedSearches {
  decorationsToReturn: DecorationSet;
  results: Range[];
}

/** 处理搜索，生成装饰和结果 */
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

  // 收集所有文本节点及其位置
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

  // 查找所有匹配项
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

  // 为每个结果创建装饰
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

/** 替换第一个匹配项 */
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

/** 重新计算下一个结果的位置偏移 */
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

/** 替换所有匹配项 */
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
  /** 搜索结果的 CSS 类名 */
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

/** 从 editor 获取 searchAndReplace storage（带类型断言） */
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
          // 触发插件重新计算
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

          // 使用 setMeta 标记事务以触发插件重新计算
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

          // 使用 setMeta 标记事务以触发插件重新计算
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

            // 检查是否有来自 setMeta 的更新信号
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
