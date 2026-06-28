/**
 * PromptEditor Component
 *
 * 提示词编辑器（基于Tiptap）
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { Flex, TextField, Separator, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Terminal, Bot, User } from "lucide-react";
import "./prompt-editor.css";
import { LabeledSelect } from "@/components/select";
import { countTokens } from "@/lib/tiktoken-utils";
import { ContextMenu } from "@/components";
import { MacroNode } from "../extensions/macro-node";
import { MacroInputRule } from "../extensions/macro-input-rule";
import { MacroAutocomplete } from "../extensions/macro-autocomplete";
import type { PromptEntryData } from "@/lib/prompt-chain.types";
import type { MacroNode as MacroNodeType } from "@/lib/macro";
import type { Editor } from "@tiptap/react";
import { htmlToNewlines, newlinesToHtml } from "@/lib/html-utils";

interface PromptEditorProps {
  entry: PromptEntryData;
  onUpdate: (updates: Partial<PromptEntryData>) => void;
  onUpdateWithId?: (entryId: string, updates: Partial<PromptEntryData>) => void;
  onMacroSelect?: (macro: MacroNodeType | null) => void;
  editorRef?: React.RefObject<Editor | null>;
  isMobile?: boolean;
}

export function PromptEditor({ entry, onUpdate, onUpdateWithId, onMacroSelect, editorRef, isMobile = false }: PromptEditorProps) {
  const { t } = useTranslation();
  // 防抖定时器引用
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 上一次的 entry.id，用于检测条目切换
  const lastEntryIdRef = useRef<string | undefined>(entry.id);
  // 是否正在从外部设置内容（避免循环更新）
  const isSettingContentRef = useRef(false);
  // 上次保存的内容（用于判断是否有未保存的更改，存储 HTML 格式用于与编辑器内容比较）
  const lastSavedContentRef = useRef<string>(
    entry.content ? newlinesToHtml(entry.content) : ""
  );
  // 编辑器内容容器引用（用于右键菜单）
  const editorContentRef = useRef<HTMLDivElement>(null);
  // 当前token数
  const [tokenCount, setTokenCount] = useState<number>(entry.token_count || 0);
  // 是否有未保存的更改
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // 角色选项（使用prefix来显示图标）
  const roleOptions = [
    { value: "system", label: t("promptChains.roleSystem"), prefix: <Terminal size={14} /> },
    { value: "user", label: t("promptChains.roleUser"), prefix: <User size={14} /> },
    { value: "assistant", label: t("promptChains.roleAssistant"), prefix: <Bot size={14} /> },
  ];

  // 防抖的更新函数
  const debouncedUpdate = useCallback(
    (updates: Partial<PromptEntryData>, savedContentHtml?: string) => {
      // 清除之前的定时器
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // 设置新的定时器（2秒防抖）
      debounceTimerRef.current = setTimeout(() => {
        onUpdate(updates);
        debounceTimerRef.current = null;
        // 更新保存状态
        if (updates.content !== undefined) {
          lastSavedContentRef.current = savedContentHtml ?? newlinesToHtml(updates.content);
          setHasUnsavedChanges(false);
        }
      }, 2000);
    },
    [onUpdate]
  );

  // 立即更新（用于非内容字段，如角色、名称）
  const immediateUpdate = useCallback(
    (updates: Partial<PromptEntryData>) => {
      onUpdate(updates);
    },
    [onUpdate]
  );

  // 创建编辑器实例
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // 禁用不需要的功能
        heading: false,
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        blockquote: false,
        horizontalRule: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
      }),
      Placeholder.configure({
        placeholder: t("promptChains.contentPlaceholder"),
      }),
      MacroNode,
      MacroInputRule,
      MacroAutocomplete,
    ],
    // 从数据库加载时，将换行符转换为 HTML（<p></p> 格式）供 Tiptap 显示
    content: entry.content ? newlinesToHtml(entry.content) : "",
    editorProps: {
      attributes: {
        class: "prompt-editor-content",
      },
    },
    onUpdate: ({ editor }) => {
      // 如果正在从外部设置内容，跳过更新
      if (isSettingContentRef.current) {
        return;
      }

      // 获取编辑器的 HTML 格式（包含 <p></p> 标签）
      const html = editor.getHTML();
      // 转换为换行符格式保存到数据库
      const content = htmlToNewlines(html);
      
      // 使用 getText() 获取纯文本并计算 token 数（使用tiktoken）
      const text = editor.getText();
      const calculatedTokenCount = countTokens(text);
      // 实时更新token数显示
      setTokenCount(calculatedTokenCount);
      onUpdate({ token_count: calculatedTokenCount });
      
      // 检查是否有未保存的更改（比较 HTML 格式，因为编辑器内部使用 HTML）
      const hasChanges = html !== lastSavedContentRef.current;
      setHasUnsavedChanges(hasChanges || debounceTimerRef.current !== null);
      
      // 使用防抖更新（保存换行符格式到数据库）
      debouncedUpdate({
        content: content,
        token_count: calculatedTokenCount,
      }, html);
    },
    onSelectionUpdate: ({ editor }) => {
      // 检测是否选中了宏节点
      const { selection } = editor.state;
      
      // 检查当前选中位置的节点
      let selectedMacroNode: MacroNodeType | null = null;
      
      editor.state.doc.nodesBetween(
        selection.from,
        selection.to,
        (node, pos) => {
          if (node.type.name === "macroNode") {
            const macroData = node.attrs.macroData 
              ? JSON.parse(node.attrs.macroData) 
              : { args: [] };
            
            selectedMacroNode = {
              name: node.attrs.macroName,
              args: macroData.args || [],
              raw: node.attrs.macroRaw,
              start: pos,
              end: pos + node.nodeSize,
            };
            return false; // 停止遍历
          }
        }
      );
      
      onMacroSelect?.(selectedMacroNode);
    },
  });

  // 立即保存当前内容（用于快捷键和切换条目时）
  const saveNow = useCallback(() => {
    if (!editor || isSettingContentRef.current) return;

    // 清除防抖定时器
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // 获取当前编辑器内容
    const html = editor.getHTML();
    const content = htmlToNewlines(html);
    const text = editor.getText();
    const calculatedTokenCount = countTokens(text);

    // 立即更新
    onUpdate({
      content: content,
      token_count: calculatedTokenCount,
    });

    // 更新保存状态
    lastSavedContentRef.current = html;
    setHasUnsavedChanges(false);
    setTokenCount(calculatedTokenCount);
  }, [editor, onUpdate]);

  // 带条目ID的保存函数（用于切换条目时保存旧条目）
  const saveNowWithId = useCallback((targetEntryId: string) => {
    if (!editor || isSettingContentRef.current) return;

    // 清除防抖定时器
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // 获取当前编辑器内容
    const html = editor.getHTML();
    const content = htmlToNewlines(html);
    const text = editor.getText();
    const calculatedTokenCount = countTokens(text);

    // 使用 onUpdateWithId 保存指定条目的内容
    if (onUpdateWithId) {
      onUpdateWithId(targetEntryId, {
        content: content,
        token_count: calculatedTokenCount,
      });
    } else {
      onUpdate({
        content: content,
        token_count: calculatedTokenCount,
      });
    }

    // 更新保存状态
    lastSavedContentRef.current = html;
    setHasUnsavedChanges(false);
    setTokenCount(calculatedTokenCount);
  }, [editor, onUpdate, onUpdateWithId]);

  // 设置 editorRef
  useEffect(() => {
    if (editorRef) {
      editorRef.current = editor;
    }
  }, [editor, editorRef]);

  // 监听 entry.id 变化，在切换条目前保存旧条目的内容
  useEffect(() => {
    if (!editor) return;

    // 检测条目切换（entry.id 变化）
    const isEntryChanged = lastEntryIdRef.current !== entry.id;
    const previousEntryId = lastEntryIdRef.current;

    // 如果切换条目且有未保存的更改，先保存旧条目的内容
    if (isEntryChanged && previousEntryId !== undefined) {
      // 获取当前编辑器内容（HTML 格式）
      const currentEditorContent = editor.getHTML();
      // 直接检查当前内容是否与已保存的内容不同
      const hasChanges = currentEditorContent !== lastSavedContentRef.current || debounceTimerRef.current !== null;
      
      if (hasChanges) {
        // 调用保存函数（setState 在 useCallback 内部，不会触发警告）
        saveNowWithId(previousEntryId);
      }
    }

    // 更新 lastEntryIdRef（在保存完成后）
    lastEntryIdRef.current = entry.id;
  }, [entry.id, editor, saveNowWithId]);

  // 当条目或外部内容改变时更新编辑器内容
  useEffect(() => {
    if (!editor) return;

    // 检测条目切换（entry.id 变化）
    const isEntryChanged = lastEntryIdRef.current !== entry.id;

    // 获取当前编辑器内容（HTML 格式）
    const currentEditorContent = editor.getHTML();
    // 从数据库加载的内容是换行符格式，需要转换为 HTML 供编辑器显示
    const newContentHtml = entry.content ? newlinesToHtml(entry.content) : "";

    // 正在编辑当前条目时，父组件的旧 content 不应回灌覆盖 Tiptap 中的新输入。
    if (!isEntryChanged && debounceTimerRef.current !== null) return;

    // 只有在内容真正不同时才更新（避免循环更新）
    if (currentEditorContent !== newContentHtml || isEntryChanged) {
      isSettingContentRef.current = true;
      // 使用 queueMicrotask 将 setContent 延迟到微任务中，避免在 React 渲染周期中调用 flushSync
      queueMicrotask(() => {
        editor.commands.setContent(newContentHtml);
        // 使用 setTimeout 确保 onUpdate 不会立即触发，并更新状态
        setTimeout(() => {
          isSettingContentRef.current = false;
          // 更新保存状态（保存 HTML 格式用于比较，因为编辑器内部使用 HTML）
          lastSavedContentRef.current = newContentHtml;
          setHasUnsavedChanges(false);
          // 重新计算token数
          if (editor) {
            const text = editor.getText();
            setTokenCount(countTokens(text));
          }
        }, 0);
      });
    }
  }, [entry.id, entry.content, editor]);

  // Ctrl+S 快捷键保存
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 检查是否是 Ctrl+S (Windows/Linux) 或 Cmd+S (Mac)
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveNow();
      }
    };

    // 添加键盘事件监听器
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [saveNow]);

  // 清理防抖定时器
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="prompt-editor-shell">
      {/* 表单区域 - 固定高度，不滚动 */}
      <div className="prompt-editor-form">
        {/* 第一行：角色选择 + 条目名称 */}
        <Flex align="center" gap="4" mb="4">
          {/* 角色选择 */}
          <LabeledSelect
            value={entry.role}
            options={roleOptions}
            onChange={(value) => {
              immediateUpdate({ role: value as "system" | "user" | "assistant" });
            }}
            size="2"
            layout="horizontal"
            gap="2"
            triggerStyle={isMobile ? { } : { minWidth: "150px" }}
            triggerLabelVisible={!isMobile}
          />

        <Separator orientation="vertical" />

          {/* 条目名称 */}
          <Flex align="center" gap="2" className="prompt-editor-entry-name-row">
            <TextField.Root
              value={entry.name}
              onChange={(e) => {
                immediateUpdate({ name: e.target.value });
              }}
              placeholder={t("promptChains.entryNameInputPlaceholder")}
              size="2"
              className="prompt-editor-entry-name-input"
            />
          </Flex>
        </Flex>
      </div>

      <div className="prompt-editor-main">
        {/* 编辑器块（带边框）- 可滚动区域，占据剩余空间 */}
        <div className="prompt-editor-frame">
          {/* 编辑器内容区 - 可滚动 */}
          <div ref={editorContentRef} className="prompt-editor-scroll-area">
            <EditorContent editor={editor} />
          </div>
        </div>

        {/* 右键菜单 */}
        <ContextMenu editor={editor} containerRef={editorContentRef} />
      </div>

      {/* 底部状态栏 - 固定 */}
      <div className="prompt-editor-statusbar">
        <Flex justify="between" align="center">
          {/* 左侧：Token数 */}
          <Text size="2" color="gray">
            {t("promptChains.tokenCount")}: {tokenCount}
          </Text>

          {/* 右侧：保存状态 */}
          <Text
            size="2"
            color={hasUnsavedChanges ? "amber" : "green"}
            weight={hasUnsavedChanges ? "medium" : "regular"}
          >
            {hasUnsavedChanges
              ? t("promptChains.unsavedChanges")
              : t("promptChains.saved")}
          </Text>
        </Flex>
      </div>
    </div>
  );
}
