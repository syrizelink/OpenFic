/**
 * PromptEditor Component
 *
 * 提示词编辑器（基于Tiptap）
 */

import { Flex, TextField, Separator, Text } from "@radix-ui/themes";
import Placeholder from "@tiptap/extension-placeholder";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Terminal, Bot, User } from "lucide-react";
import { useEffect, useRef, useCallback, useState } from "react";

import "./prompt-editor.css";
import { useTranslation } from "react-i18next";

import { ContextMenu } from "@/components";
import { LabeledSelect } from "@/components/select";
import { newlinesToHtml } from "@/lib/html-utils";
import type { PromptEntryData } from "@/lib/prompt-chain.types";
import { countTokens } from "@/lib/tiktoken-utils";

interface PromptEditorProps {
  entry: PromptEntryData;
  onUpdate: (updates: Partial<PromptEntryData>) => void;
  onUpdateWithId?: (entryId: string, updates: Partial<PromptEntryData>) => void;
  isMobile?: boolean;
}

export function PromptEditor({
  entry,
  onUpdate,
  onUpdateWithId,
  isMobile = false,
}: PromptEditorProps) {
  const { t } = useTranslation();
  // 上一次的 entry.id，用于检测条目切换
  const lastEntryIdRef = useRef<string | undefined>(entry.id);
  // Tiptap 事件处理函数在初始化后不会随 React props 更新，需通过 ref 使用最新上下文。
  const currentEntryIdRef = useRef(entry.id ?? "");
  const onUpdateRef = useRef(onUpdate);
  const onUpdateWithIdRef = useRef(onUpdateWithId);
  // 是否正在从外部设置内容（避免循环更新）
  const isSettingContentRef = useRef(false);
  // 最近一次从编辑器同步到父组件的条目内容，避免父组件回显重置光标。
  const lastSyncedEntryRef = useRef({ id: entry.id, content: entry.content });
  // 上次保存的内容（用于判断是否有未保存的更改，存储 HTML 格式用于与编辑器内容比较）
  const lastSavedContentRef = useRef<string>(
    entry.content ? newlinesToHtml(entry.content, true) : "",
  );
  // 编辑器内容容器引用（用于右键菜单）
  const editorContentRef = useRef<HTMLDivElement>(null);
  // 当前token数
  const [tokenCount, setTokenCount] = useState<number>(entry.token_count || 0);

  currentEntryIdRef.current = entry.id ?? "";
  onUpdateRef.current = onUpdate;
  onUpdateWithIdRef.current = onUpdateWithId;

  // 角色选项（使用prefix来显示图标）
  const roleOptions = [
    { value: "system", label: t("promptChains.roleSystem"), prefix: <Terminal size={14} /> },
    { value: "user", label: t("promptChains.roleUser"), prefix: <User size={14} /> },
    { value: "assistant", label: t("promptChains.roleAssistant"), prefix: <Bot size={14} /> },
  ];

  // 立即更新（用于非内容字段，如角色、名称）
  const immediateUpdate = useCallback((updates: Partial<PromptEntryData>) => {
    if (onUpdateWithIdRef.current) {
      onUpdateWithIdRef.current(currentEntryIdRef.current, updates);
      return;
    }

    onUpdateRef.current(updates);
  }, []);

  const updateEntry = useCallback((entryId: string, updates: Partial<PromptEntryData>) => {
    if (onUpdateWithIdRef.current) {
      onUpdateWithIdRef.current(entryId, updates);
      return;
    }

    onUpdateRef.current(updates);
  }, []);

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
    ],
    // 从数据库加载时，将换行符转换为 HTML（<p></p> 格式）供 Tiptap 显示
    content: entry.content ? newlinesToHtml(entry.content, true) : "",
    parseOptions: {
      preserveWhitespace: "full",
    },
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

      // 直接从 Tiptap 文档导出纯文本，避免对 HTML 做有损的二次解析。
      const html = editor.getHTML();
      const content = editor.getText({ blockSeparator: "\n" });

      const calculatedTokenCount = countTokens(content);
      // 实时更新token数显示
      setTokenCount(calculatedTokenCount);

      // 版本保存依赖父级 entries 状态，正文必须在当前事件中同步更新。
      const entryId = currentEntryIdRef.current;
      lastSyncedEntryRef.current = { id: entryId, content };
      updateEntry(entryId, {
        content: content,
        token_count: calculatedTokenCount,
      });
      lastSavedContentRef.current = html;
    },
  });

  // 立即保存当前内容（用于快捷键和切换条目时）
  const saveNow = useCallback(() => {
    if (!editor || isSettingContentRef.current) return;

    // 获取当前编辑器内容
    const html = editor.getHTML();
    const content = editor.getText({ blockSeparator: "\n" });
    const calculatedTokenCount = countTokens(content);

    // 立即更新
    lastSyncedEntryRef.current = { id: currentEntryIdRef.current, content };
    updateEntry(currentEntryIdRef.current, {
      content: content,
      token_count: calculatedTokenCount,
    });

    // 更新保存状态
    lastSavedContentRef.current = html;
    setTokenCount(calculatedTokenCount);
  }, [editor, updateEntry]);

  // 带条目ID的保存函数（用于切换条目时保存旧条目）
  const saveNowWithId = useCallback(
    (targetEntryId: string) => {
      if (!editor || isSettingContentRef.current) return;

      // 获取当前编辑器内容
      const html = editor.getHTML();
      const content = editor.getText({ blockSeparator: "\n" });
      const calculatedTokenCount = countTokens(content);

      lastSyncedEntryRef.current = { id: targetEntryId, content };
      updateEntry(targetEntryId, {
        content: content,
        token_count: calculatedTokenCount,
      });

      // 更新保存状态
      lastSavedContentRef.current = html;
      setTokenCount(calculatedTokenCount);
    },
    [editor, updateEntry],
  );

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
      const hasChanges = currentEditorContent !== lastSavedContentRef.current;

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

    const isLocalContentEcho =
      lastSyncedEntryRef.current.id === entry.id &&
      lastSyncedEntryRef.current.content === entry.content;
    if (isLocalContentEcho) return;

    // 获取当前编辑器内容（HTML 格式）
    const currentEditorContent = editor.getHTML();
    // 从数据库加载的内容是换行符格式，需要转换为 HTML 供编辑器显示
    const newContentHtml = entry.content ? newlinesToHtml(entry.content, true) : "";

    // 只有在内容真正不同时才更新（避免循环更新）
    if (currentEditorContent !== newContentHtml) {
      isSettingContentRef.current = true;
      // 使用 queueMicrotask 将 setContent 延迟到微任务中，避免在 React 渲染周期中调用 flushSync
      queueMicrotask(() => {
        editor.commands.setContent(newContentHtml, {
          emitUpdate: false,
          parseOptions: {
            preserveWhitespace: "full",
          },
        });
        // 使用 setTimeout 确保 onUpdate 不会立即触发，并更新状态
        setTimeout(() => {
          isSettingContentRef.current = false;
          lastSyncedEntryRef.current = { id: entry.id, content: entry.content };
          // 更新保存状态（保存 HTML 格式用于比较，因为编辑器内部使用 HTML）
          lastSavedContentRef.current = newContentHtml;
          // 重新计算token数
          if (editor) {
            const text = editor.getText({ blockSeparator: "\n" });
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

  return (
    <div className="prompt-editor-shell">
      {/* 表单区域 - 固定高度，不滚动 */}
      <div className="prompt-editor-form">
        {/* 第一行：角色选择 + 条目名称 */}
        <Flex
          align="center"
          gap="4"
          mb="4"
        >
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
            triggerStyle={isMobile ? {} : { minWidth: "150px" }}
            triggerLabelVisible={!isMobile}
          />

          <Separator orientation="vertical" />

          {/* 条目名称 */}
          <Flex
            align="center"
            gap="2"
            className="prompt-editor-entry-name-row"
          >
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
          <div
            ref={editorContentRef}
            className="prompt-editor-scroll-area"
          >
            <EditorContent editor={editor} />
          </div>
        </div>

        {/* 右键菜单 */}
        <ContextMenu
          editor={editor}
          containerRef={editorContentRef}
        />
      </div>

      {/* 底部状态栏 - 固定 */}
      <div className="prompt-editor-statusbar">
        <Flex
          justify="between"
          align="center"
        >
          {/* 左侧：Token数 */}
          <Text
            size="2"
            color="gray"
          >
            {t("promptChains.tokenCount")}: {tokenCount}
          </Text>

          {/* 右侧：工作副本同步状态 */}
          <Text
            size="2"
            color="green"
            weight="regular"
          >
            {t("promptChains.saved")}
          </Text>
        </Flex>
      </div>
    </div>
  );
}
