/**
 * Find Replace Panel
 *
 * 查找和替换面板组件，提供搜索输入、结果导航和替换功能。
 */

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Flex,
  IconButton,
  Text,
  Separator,
  Tooltip,
} from "@radix-ui/themes";
import {
  X,
  ChevronUp,
  ChevronDown,
  Replace,
  ReplaceAll,
  Search,
} from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import type { Editor } from "@tiptap/react";

interface FindReplacePanelProps {
  editor: Editor;
  /** 是否显示替换区域（false 时只显示查找） */
  showReplace: boolean;
  /** 关闭面板的回调 */
  onClose: () => void;
}

/** 搜索框最大宽度（与编辑器内容一致） */
const PANEL_MAX_WIDTH = 800;

/** 搜索输入框样式 */
const inputStyle: React.CSSProperties = {
  flex: 1,
  height: 32,
  padding: "0 8px",
  paddingLeft: 32, // 为搜索图标留出空间
  paddingRight: 56, // 为计数器留出空间
  fontSize: 14,
  border: "1px solid var(--gray-a5)",
  borderRadius: 6,
  background: "var(--color-background)",
  color: "var(--gray-12)",
  outline: "none",
  transition: "border-color 0.2s ease, box-shadow 0.2s ease",
};

/** 替换输入框样式 */
const replaceInputStyle: React.CSSProperties = {
  flex: 1,
  height: 32,
  padding: "0 8px",
  paddingLeft: 12,
  fontSize: 14,
  border: "1px solid var(--gray-a5)",
  borderRadius: 6,
  background: "var(--color-background)",
  color: "var(--gray-12)",
  outline: "none",
  transition: "border-color 0.2s ease, box-shadow 0.2s ease",
};

export function FindReplacePanel({
  editor,
  showReplace,
  onClose,
}: FindReplacePanelProps) {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [replaceTerm, setReplaceTerm] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const [replaceFocused, setReplaceFocused] = useState(false);

  // 搜索结果状态（从 editor storage 同步）
  const [resultCount, setResultCount] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);

  // 同步搜索词到编辑器
  useEffect(() => {
    editor.commands.setSearchTerm(searchTerm);
  }, [editor, searchTerm]);

  // 监听 editor 更新，同步搜索结果到组件状态
  useEffect(() => {
    const updateResults = () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const storage = (editor as any).storage.searchAndReplace as
        | {
            results: Array<{ from: number; to: number }>;
            resultIndex: number;
          }
        | undefined;
      const results = storage?.results ?? [];
      const resultIndex = storage?.resultIndex ?? 0;
      setResultCount(results.length);
      setCurrentIndex(results.length > 0 ? resultIndex + 1 : 0);
    };

    // 初始更新
    updateResults();

    // 监听事务更新
    editor.on("transaction", updateResults);
    return () => {
      editor.off("transaction", updateResults);
    };
  }, [editor]);

  // 同步替换词到编辑器
  useEffect(() => {
    editor.commands.setReplaceTerm(replaceTerm);
  }, [editor, replaceTerm]);

  // 关闭时清除搜索
  useEffect(() => {
    return () => {
      editor.commands.setSearchTerm("");
      editor.commands.setReplaceTerm("");
    };
  }, [editor]);

  // ESC 键关闭面板
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // 滚动到当前搜索结果
  const scrollToCurrentResult = useCallback(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const storage = (editor as any).storage.searchAndReplace;
    const results = storage?.results ?? [];
    const resultIndex = storage?.resultIndex ?? 0;
    const currentResult = results[resultIndex];

    if (currentResult) {
      // 使用 ProseMirror 的坐标系统获取位置并滚动
      const { from } = currentResult;
      const coords = editor.view.coordsAtPos(from);
      const editorElement = editor.view.dom.closest(
        ".tiptap-editor-wrapper"
      ) as HTMLElement;

      if (editorElement && coords) {
        const editorRect = editorElement.getBoundingClientRect();
        const relativeTop =
          coords.top - editorRect.top + editorElement.scrollTop;

        // 滚动使结果在视图中居中
        editorElement.scrollTo({
          top: relativeTop - editorRect.height / 2,
          behavior: "smooth",
        });
      }
    }
  }, [editor]);

  const handlePrevious = useCallback(() => {
    editor.commands.previousSearchResult();
    // 延迟滚动，等待 DOM 更新
    setTimeout(scrollToCurrentResult, 10);
  }, [editor, scrollToCurrentResult]);

  const handleNext = useCallback(() => {
    editor.commands.nextSearchResult();
    // 延迟滚动，等待 DOM 更新
    setTimeout(scrollToCurrentResult, 10);
  }, [editor, scrollToCurrentResult]);

  const handleReplace = useCallback(() => {
    editor.commands.replace();
  }, [editor]);

  const handleReplaceAll = useCallback(() => {
    editor.commands.replaceAll();
  }, [editor]);

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.06, ease: "easeOut" }}
      style={{
        overflow: "hidden",
        background: "var(--color-background)",
      }}
    >
      <Box py="3">
        {/* 居中容器，与编辑器内容宽度一致 */}
        <Box
          style={{
            maxWidth: PANEL_MAX_WIDTH,
            margin: "0 auto",
            padding: "0 24px",
          }}
        >
          <Flex direction="column" gap="2">
            {/* 查找行 */}
            <Flex align="center" gap="2">
              {/* 搜索输入框容器 */}
              <Box style={{ flex: 1, position: "relative" }}>
                {/* 搜索图标 */}
                <Box
                  style={{
                    position: "absolute",
                    left: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    pointerEvents: "none",
                    color: "var(--gray-a9)",
                  }}
                >
                  <Search size={14} />
                </Box>

                {/* 搜索输入框 */}
                <input
                  type="text"
                  placeholder={t("editor.findPlaceholder")}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  autoFocus
                  style={{
                    ...inputStyle,
                    width: "100%",
                    borderColor: searchFocused
                      ? "var(--gray-a8)"
                      : "var(--gray-a5)",
                    boxShadow: searchFocused
                      ? "0 0 0 1px var(--gray-a4)"
                      : "none",
                  }}
                />

                {/* 结果计数（在搜索框内右侧） */}
                <Text
                  size="1"
                  color="gray"
                  style={{
                    position: "absolute",
                    right: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    pointerEvents: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  {resultCount > 0 ? `${currentIndex}/${resultCount}` : "0/0"}
                </Text>
              </Box>

              {/* 上一个/下一个 */}
              <Flex gap="1">
                <Tooltip content={t("editor.previousResult")}>
                  <IconButton
                    variant="ghost"
                    size="1"
                    disabled={resultCount === 0}
                    onClick={handlePrevious}
                    aria-label={t("editor.previousResult")}
                  >
                    <ChevronUp size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip content={t("editor.nextResult")}>
                  <IconButton
                    variant="ghost"
                    size="1"
                    disabled={resultCount === 0}
                    onClick={handleNext}
                    aria-label={t("editor.nextResult")}
                  >
                    <ChevronDown size={16} />
                  </IconButton>
                </Tooltip>
              </Flex>

              <Separator orientation="vertical" size="1" />

              {/* 关闭按钮 */}
              <Tooltip content={t("common.close")}>
                <IconButton
                  variant="ghost"
                  size="1"
                  onClick={onClose}
                  aria-label={t("common.close")}
                >
                  <X size={16} />
                </IconButton>
              </Tooltip>
            </Flex>

            {/* 替换行 */}
            {showReplace && (
              <Flex align="center" gap="2">
                {/* 替换输入框 */}
                <Box style={{ flex: 1 }}>
                  <input
                    type="text"
                    placeholder={t("editor.replacePlaceholder")}
                    value={replaceTerm}
                    onChange={(e) => setReplaceTerm(e.target.value)}
                    onFocus={() => setReplaceFocused(true)}
                    onBlur={() => setReplaceFocused(false)}
                    style={{
                      ...replaceInputStyle,
                      width: "100%",
                      borderColor: replaceFocused
                        ? "var(--gray-a8)"
                        : "var(--gray-a5)",
                      boxShadow: replaceFocused
                        ? "0 0 0 1px var(--gray-a4)"
                        : "none",
                    }}
                  />
                </Box>

                {/* 替换/全部替换按钮 */}
                <Flex gap="1">
                  <Tooltip content={t("editor.replace")}>
                    <IconButton
                      variant="ghost"
                      size="1"
                      disabled={resultCount === 0}
                      onClick={handleReplace}
                      aria-label={t("editor.replace")}
                    >
                      <Replace size={16} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip content={t("editor.replaceAll")}>
                    <IconButton
                      variant="ghost"
                      size="1"
                      disabled={resultCount === 0}
                      onClick={handleReplaceAll}
                      aria-label={t("editor.replaceAll")}
                    >
                      <ReplaceAll size={16} />
                    </IconButton>
                  </Tooltip>
                </Flex>

                {/* 占位保持与上一行对齐 */}
                <Box style={{ width: 28 }} />
              </Flex>
            )}
          </Flex>
        </Box>
      </Box>
    </motion.div>
  );
}
