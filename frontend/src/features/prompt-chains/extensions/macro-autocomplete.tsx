/**
 * MacroAutocomplete - Tiptap 宏补全扩展
 *
 * 检测 {{ 输入并显示宏补全建议面板。
 */

/* oxlint-disable react-refresh/only-export-components */

import { useState, useCallback, useEffect } from "react";
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import { ReactRenderer } from "@tiptap/react";
import { AutocompletePopover } from "@/components";
import type { AutocompleteItem } from "@/components";
import { getMacroCompletions, findUncompletedMacro } from "@/lib/macro";

const PLUGIN_KEY = new PluginKey("macroAutocomplete");

interface AutocompleteState {
  visible: boolean;
  items: AutocompleteItem[];
  hint?: string;
  anchorRect: { top: number; left: number } | null;
  selectedIndex: number;
  replaceFrom: number;
  filterText: string; // 当前输入的过滤文本（用于高亮）
}

const initialState: AutocompleteState = {
  visible: false,
  items: [],
  hint: undefined,
  anchorRect: null,
  selectedIndex: 0,
  replaceFrom: -1,
  filterText: "",
};

/** 获取光标位置的视口坐标 */
function getCursorRect(view: EditorView): { top: number; left: number } | null {
  const { from } = view.state.selection;
  const coords = view.coordsAtPos(from);
  if (!coords) return null;
  
  return {
    top: coords.bottom + 4, // 光标下方留出间距
    left: coords.left,
  };
}

/** React 包装组件，用于管理状态 */
function AutocompleteWrapper({
  initialState,
  onSelect,
  onClose,
  stateRef,
}: {
  initialState: AutocompleteState;
  onSelect: (item: AutocompleteItem) => void;
  onClose: () => void;
  stateRef: React.MutableRefObject<{
    updateState: (state: Partial<AutocompleteState>) => void;
  } | null>;
}) {
  const [state, setState] = useState<AutocompleteState>(initialState);

  // 暴露更新方法给外部
  useEffect(() => {
    stateRef.current = {
      updateState: (newState: Partial<AutocompleteState>) => {
        setState((prev) => ({ ...prev, ...newState }));
      },
    };
    return () => {
      stateRef.current = null;
    };
  }, [stateRef]);

  const handleSelect = useCallback(
    (item: AutocompleteItem) => {
      onSelect(item);
    },
    [onSelect]
  );

  const handleSelectedIndexChange = useCallback((index: number) => {
    setState((prev) => ({ ...prev, selectedIndex: index }));
  }, []);

  return (
    <AutocompletePopover
      items={state.items}
      anchorRect={state.anchorRect}
      visible={state.visible}
      selectedIndex={state.selectedIndex}
      onSelect={handleSelect}
      onSelectedIndexChange={handleSelectedIndexChange}
      onClose={onClose}
      hint={state.hint}
      filterText={state.filterText}
    />
  );
}

export const MacroAutocomplete = Extension.create({
  name: "macroAutocomplete",

  addProseMirrorPlugins() {
    const editor = this.editor;
    
    // 状态引用
    const stateRef: React.MutableRefObject<{
      updateState: (state: Partial<AutocompleteState>) => void;
    } | null> = { current: null };
    
    // 当前状态
    let currentState: AutocompleteState = { ...initialState };
    
    // ReactRenderer 实例
    let renderer: ReactRenderer | null = null;

    const updateAutocomplete = (view: EditorView) => {
      const { $from } = view.state.selection;
      
      // 获取光标前的所有文本
      const textBefore = $from.parent.textBetween(
        0,
        $from.parentOffset,
        undefined,
        "\ufffc"
      );
      
      // 检查是否有未闭合的宏
      const uncompletedMacro = findUncompletedMacro(textBefore);
      
      if (uncompletedMacro === null) {
        // 没有未闭合的宏，隐藏补全
        if (currentState.visible) {
          currentState = { ...initialState };
          stateRef.current?.updateState(currentState);
        }
        return;
      }
      
      // 获取补全建议
      const result = getMacroCompletions(uncompletedMacro);
      
      // 如果没有补全项也没有提示，隐藏
      if (result.items.length === 0 && !result.hint) {
        if (currentState.visible) {
          currentState = { ...initialState };
          stateRef.current?.updateState(currentState);
        }
        return;
      }
      
      // 计算锚点位置
      const anchorRect = getCursorRect(view);
      
      // 计算需要替换的起始位置
      // 找到最后一个 :: 分隔符的位置，如果没有则从 {{ 之后开始
      const macroStartPos = $from.pos - uncompletedMacro.length; // {{ 之后的位置
      const lastSeparatorIndex = uncompletedMacro.lastIndexOf("::");
      
      let replaceFrom: number;
      if (lastSeparatorIndex >= 0) {
        // 从最后一个 :: 之后开始替换
        replaceFrom = macroStartPos + lastSeparatorIndex + 2;
      } else {
        // 没有分隔符，从 {{ 之后开始替换（一级补全）
        replaceFrom = macroStartPos;
      }
      // 计算当前输入的过滤文本（用于高亮）
      const filterText = lastSeparatorIndex >= 0 
        ? uncompletedMacro.slice(lastSeparatorIndex + 2)
        : uncompletedMacro;
      
      // 更新状态
      currentState = {
        visible: true,
        items: result.items,
        hint: result.hint,
        anchorRect,
        selectedIndex: 0,
        replaceFrom,
        filterText,
      };
      
      stateRef.current?.updateState(currentState);
    };

    const handleSelect = (item: AutocompleteItem) => {
      if (!currentState.visible) return;
      
      const { state: editorState } = editor;
      const { from } = editorState.selection;
      
      // 替换从 replaceFrom 到当前光标位置
      const replaceFrom = currentState.replaceFrom;
      const replaceTo = from;
      
      // 插入补全文本
      editor
        .chain()
        .focus()
        .deleteRange({ from: replaceFrom, to: replaceTo })
        .insertContentAt(replaceFrom, item.insertText)
        .run();
      
      // 处理光标偏移
      if (item.cursorOffset && item.cursorOffset < 0) {
        const newPos = replaceFrom + item.insertText.length + item.cursorOffset;
        editor.commands.setTextSelection(newPos);
      }
      
      // 隐藏补全
      currentState = { ...initialState };
      stateRef.current?.updateState(currentState);
    };

    const handleClose = () => {
      currentState = { ...initialState };
      stateRef.current?.updateState(currentState);
    };

    return [
      new Plugin({
        key: PLUGIN_KEY,

        view() {
          // 创建容器
          const container = document.createElement("div");
          container.className = "macro-autocomplete-container";
          document.body.appendChild(container);

          // 创建 React 渲染器
          renderer = new ReactRenderer(AutocompleteWrapper, {
            editor,
            props: {
              initialState,
              onSelect: handleSelect,
              onClose: handleClose,
              stateRef,
            },
          });

          container.appendChild(renderer.element);

          return {
            update(view) {
              updateAutocomplete(view);
            },
            destroy() {
              renderer?.destroy();
              container.remove();
            },
          };
        },

        props: {
          handleKeyDown(_view, event) {
            if (!currentState.visible) return false;
            
            // 让 AutocompletePopover 处理键盘事件
            // 这里只需要阻止默认行为
            if (
              event.key === "ArrowUp" ||
              event.key === "ArrowDown" ||
              event.key === "Enter" ||
              event.key === "Tab" ||
              event.key === "Escape"
            ) {
              // 对于 Enter 和 Tab，如果有补全项则触发选择
              if (
                (event.key === "Enter" || event.key === "Tab") &&
                currentState.items.length > 0
              ) {
                event.preventDefault();
                handleSelect(currentState.items[currentState.selectedIndex]);
                return true;
              }
              
              if (event.key === "Escape") {
                event.preventDefault();
                handleClose();
                return true;
              }
              
              // ↑/↓ 由 AutocompletePopover 的 document listener 处理
              return false;
            }
            
            return false;
          },
        },
      }),
    ];
  },
});
