/**
 * PromptChainsPage Component
 *
 * 提示词链管理页面。
 */

import { Box, Flex, IconButton, Tooltip } from "@radix-ui/themes";
import { List } from "lucide-react";
import { motion } from "motion/react";
import { useState, useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Panel, Group, Separator, type PanelImperativeHandle } from "react-resizable-panels";

import "./prompt-chains-page.css";
import { useSearchParams } from "react-router";
import { v4 as uuidv4 } from "uuid";

import { ConfirmDialog, PromptChainDialog } from "@/components";
import { MobileAppSidebarTrigger } from "@/features/app-shell";
import { fetchPromptChainsMetadata, compilePromptChain, resetPromptChain } from "@/lib/api-client";
import type { PromptEntryData, CompileResponse } from "@/lib/prompt-chain.types";
import type { PromptChainsMetadata } from "@/lib/prompt-chain.types";

import { EntriesSidebar } from "../components/entries-sidebar";
import { PromptEditor } from "../components/prompt-editor";
import { VersionHistorySidebar } from "../components/version-history-sidebar";
import { usePromptChain } from "../hooks/use-prompt-chain";

const MotionBox = motion.create(Box);

const DEFAULT_PROMPT_ID = "builtin-agent--explore";
const VERSION_HISTORY_COLLAPSED_SIZE = 36;
const VERSION_HISTORY_MIN_SIZE = 72;

function getInitialPromptSelection(searchParams: URLSearchParams): string {
  return searchParams.get("prompt") || DEFAULT_PROMPT_ID;
}

function getDefaultPromptId(metadata: PromptChainsMetadata): string | null {
  const promptIds = (metadata.categories ?? []).flatMap((category) =>
    category.prompts.map((prompt) => prompt.id),
  );
  return promptIds.includes(DEFAULT_PROMPT_ID) ? DEFAULT_PROMPT_ID : (promptIds[0] ?? null);
}

function getEffectivePromptId(
  metadata: PromptChainsMetadata | null,
  promptId: string | null,
): string | null {
  if (!metadata) return promptId;
  const promptIds = (metadata.categories ?? []).flatMap((category) =>
    category.prompts.map((prompt) => prompt.id),
  );
  return promptId && promptIds.includes(promptId) ? promptId : getDefaultPromptId(metadata);
}

export function PromptChainsPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const initialPromptId = getInitialPromptSelection(searchParams);

  // 元数据状态
  const [metadata, setMetadata] = useState<PromptChainsMetadata | null>(null);

  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(initialPromptId);

  // 当前编辑的条目ID
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);

  // 待删除的条目ID
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);

  // 高亮的条目ID（用于新建后的闪烁动画）
  const [highlightEntryId, setHighlightEntryId] = useState<string | null>(null);

  // 编译相关状态
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);
  const [compileDialogOpen, setCompileDialogOpen] = useState(false);

  // 重置相关状态
  const [isResetting, setIsResetting] = useState(false);

  // 响应式检测
  const [isMobile, setIsMobile] = useState(false);
  const [mobileEntriesOpen, setMobileEntriesOpen] = useState(false);
  const [isVersionHistoryCollapsed, setIsVersionHistoryCollapsed] = useState(false);
  const versionHistoryPanelRef = useRef<PanelImperativeHandle | null>(null);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // 加载元数据
  useEffect(() => {
    async function loadMetadata() {
      try {
        const data = await fetchPromptChainsMetadata();
        setMetadata(data);
      } catch (error) {
        console.error("Failed to load prompt chains metadata:", error);
      }
    }
    loadMetadata();
  }, []);

  const effectivePromptId = getEffectivePromptId(metadata, selectedPromptId);

  const shouldLoadChain = !!effectivePromptId;
  const {
    currentVersion,
    versions,
    entries,
    setEntries,
    isLoading,
    loadVersion,
    saveVersion,
    isSaving,
    hasUnsavedChanges,
    isDefault,
    resetWorkingCopy,
  } = usePromptChain(effectivePromptId ?? "");

  // 获取当前选中的条目（如果没有选中且有条目，自动选择第一个）
  const actualSelectedId: string | null =
    selectedEntryId || (entries.length > 0 ? entries[0].id || null : null);
  const selectedEntry = entries.find((e) => e.id === actualSelectedId) || null;

  // 更新条目（使用 useCallback 优化）
  const handleUpdateEntry = useCallback(
    (entryId: string, updates: Partial<PromptEntryData>) => {
      setEntries((prev) => {
        // 检查是否有实际变化，避免不必要的数组重建
        const entry = prev.find((e) => e.id === entryId);
        if (!entry) return prev;

        // 检查是否有实际变化
        const hasChanges = Object.keys(updates).some(
          (key) => entry[key as keyof PromptEntryData] !== updates[key as keyof PromptEntryData],
        );

        if (!hasChanges) return prev;

        // 有变化时才创建新数组
        return prev.map((e) => (e.id === entryId ? { ...e, ...updates } : e));
      });
    },
    [setEntries],
  );

  // 切换条目启用状态（使用 useCallback 优化）
  const handleToggleEntry = useCallback(
    (entryId: string) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === entryId ? { ...e, is_enabled: !e.is_enabled } : e)),
      );
    },
    [setEntries],
  );

  // 删除条目（确认后）
  const confirmDeleteEntry = () => {
    if (deletingEntryId) {
      setEntries((prev) => prev.filter((e) => e.id !== deletingEntryId));
      // 如果删除的是当前选中的，清除选中
      if (deletingEntryId === selectedEntryId) {
        setSelectedEntryId(null);
      }
      setDeletingEntryId(null);
    }
  };

  // 新建条目
  const handleCreateEntry = () => {
    const newEntryId = `temp-${Date.now()}`;
    const newEntry: PromptEntryData = {
      id: newEntryId,
      uid: uuidv4(),
      name: t("promptChains.newEntryName"),
      role: "user",
      content: "",
      order_index: entries.length,
      is_enabled: true,
      token_count: 0,
    };

    setEntries((prev) => [...prev, newEntry]);
    setSelectedEntryId(newEntryId);

    // 设置高亮动画
    setHighlightEntryId(newEntryId);
    setTimeout(() => {
      setHighlightEntryId(null);
    }, 1000);
  };

  const handleSelectEntry = useCallback(
    (entryId: string) => {
      setSelectedEntryId(entryId);
      if (isMobile) {
        setMobileEntriesOpen(false);
      }
    },
    [isMobile],
  );

  // 编译提示词链
  const handleCompile = useCallback(async () => {
    if (!effectivePromptId) return;

    setIsCompiling(true);
    setCompileDialogOpen(true);
    setCompileResult(null);

    try {
      const result = await compilePromptChain(effectivePromptId);
      setCompileResult(result);
    } catch (error) {
      console.error("Failed to compile prompt chain:", error);
    } finally {
      setIsCompiling(false);
    }
  }, [effectivePromptId]);

  // 重置到默认
  const handleReset = useCallback(async () => {
    if (!effectivePromptId || isSaving) return;

    setIsResetting(true);
    try {
      const result = await resetPromptChain(effectivePromptId);
      const entriesData: PromptEntryData[] = result.entries.map((e) => ({
        id: e.id,
        uid: e.uid,
        name: e.name,
        role: e.role,
        content: e.content,
        order_index: e.orderIndex,
        is_enabled: e.isEnabled,
        token_count: e.tokenCount,
      }));
      await resetWorkingCopy(result.version.id, entriesData);
    } catch (error) {
      console.error("Failed to reset prompt chain:", error);
    } finally {
      setIsResetting(false);
    }
  }, [effectivePromptId, isSaving, resetWorkingCopy]);

  const handleSaveVersion = useCallback(
    (note?: string) => {
      if (isResetting || !hasUnsavedChanges) return;

      saveVersion(note);
    },
    [hasUnsavedChanges, isResetting, saveVersion],
  );

  const handleVersionHistoryCollapsedChange = () => {
    const panel = versionHistoryPanelRef.current;
    if (!panel) return;

    if (panel.isCollapsed()) {
      panel.expand();
    } else {
      panel.collapse();
    }

    setIsVersionHistoryCollapsed(panel.isCollapsed());
  };

  const handleVersionHistoryResize = () => {
    setIsVersionHistoryCollapsed(versionHistoryPanelRef.current?.isCollapsed() ?? false);
  };

  const sidebarContent = (
    <Group
      orientation="vertical"
      className="prompt-chains-page-sidebar-group"
    >
      <Panel
        id="entries-sidebar"
        defaultSize="60%"
        minSize={30}
      >
        <EntriesSidebar
          promptCategories={metadata?.categories ?? []}
          selectedPromptId={effectivePromptId}
          onPromptChange={setSelectedPromptId}
          entries={shouldLoadChain ? entries : []}
          selectedEntryId={actualSelectedId}
          onSelectEntry={handleSelectEntry}
          onToggleEntry={handleToggleEntry}
          onDeleteEntry={setDeletingEntryId}
          onReorderEntries={setEntries}
          onCreateEntry={handleCreateEntry}
          currentVersion={currentVersion}
          versions={versions}
          onSave={handleSaveVersion}
          onReset={handleReset}
          onCompile={handleCompile}
          isLoading={isLoading}
          isResetting={isResetting}
          isSaving={isSaving}
          isCompiling={isCompiling}
          hasUnsavedChanges={hasUnsavedChanges}
          isDefault={isDefault}
          highlightEntryId={highlightEntryId}
        />
      </Panel>

      <Separator
        className={
          isVersionHistoryCollapsed
            ? "resize-handle prompt-chains-page-sidebar-separator prompt-chains-page-sidebar-separator--disabled"
            : "resize-handle prompt-chains-page-sidebar-separator"
        }
        disabled={isVersionHistoryCollapsed}
      />

      <Panel
        id="version-history-sidebar"
        panelRef={versionHistoryPanelRef}
        defaultSize="40%"
        minSize={`${VERSION_HISTORY_MIN_SIZE}px`}
        collapsible
        collapsedSize={VERSION_HISTORY_COLLAPSED_SIZE}
        onResize={handleVersionHistoryResize}
      >
        <VersionHistorySidebar
          promptId={effectivePromptId ?? ""}
          versions={versions}
          currentVersion={currentVersion}
          onCheckout={loadVersion}
          isCollapsed={isVersionHistoryCollapsed}
          onCollapsedChange={handleVersionHistoryCollapsedChange}
        />
      </Panel>
    </Group>
  );

  return (
    <Box className="prompt-chains-page-root">
      {/* 主内容区 - resizable panels */}
      <Box className="prompt-chains-page-main">
        {!isMobile ? (
          <Group
            orientation="horizontal"
            className="prompt-chains-page-group"
          >
            {/* 左侧边栏：条目列表 */}
            <Panel
              id="left-sidebar"
              defaultSize={300}
              minSize={250}
              maxSize={420}
              collapsible={false}
            >
              <Box className="prompt-chains-page-panel-shell prompt-chains-page-panel-shell--left">
                {sidebarContent}
              </Box>
            </Panel>

            <Separator className="resize-handle writing-page-separator" />

            {/* 中间栏：编辑器 */}
            <Panel
              id="editor"
              minSize={30}
            >
              <div className="prompt-chains-page-editor-panel">
                {!shouldLoadChain ? (
                  <Flex
                    align="center"
                    justify="center"
                    className="prompt-chains-page-empty-state"
                  >
                    {t("promptChains.selectPrompt")}
                  </Flex>
                ) : selectedEntry && selectedEntry.id ? (
                  <PromptEditor
                    entry={selectedEntry}
                    onUpdate={(updates) => handleUpdateEntry(selectedEntry.id!, updates)}
                    onUpdateWithId={handleUpdateEntry}
                    isMobile={false}
                  />
                ) : (
                  <Flex
                    align="center"
                    justify="center"
                    className="prompt-chains-page-empty-state"
                  >
                    {t("promptChains.selectEntryToEdit")}
                  </Flex>
                )}
              </div>
            </Panel>
          </Group>
        ) : (
          <Flex className="prompt-chains-page-mobile-layout">
            <Flex
              align="center"
              justify="between"
              px="3"
              py="2"
              className="prompt-chains-page-mobile-topbar"
            >
              <Flex
                align="center"
                gap="1"
              >
                <MobileAppSidebarTrigger />
                <Tooltip content={t("promptChains.viewEntries")}>
                  <IconButton
                    variant="ghost"
                    size="2"
                    aria-label={t("promptChains.viewEntries")}
                    onClick={() => setMobileEntriesOpen((prev) => !prev)}
                  >
                    <List size={18} />
                  </IconButton>
                </Tooltip>
              </Flex>

              <Box className="prompt-chains-page-mobile-topbar-side" />
            </Flex>

            <div className="prompt-chains-page-editor-panel">
              {!shouldLoadChain ? (
                <Flex
                  align="center"
                  justify="center"
                  className="prompt-chains-page-empty-state"
                >
                  {t("promptChains.selectPrompt")}
                </Flex>
              ) : selectedEntry && selectedEntry.id ? (
                <PromptEditor
                  entry={selectedEntry}
                  onUpdate={(updates) => handleUpdateEntry(selectedEntry.id!, updates)}
                  onUpdateWithId={handleUpdateEntry}
                  isMobile={true}
                />
              ) : (
                <Flex
                  align="center"
                  justify="center"
                  className="prompt-chains-page-empty-state"
                >
                  {t("promptChains.selectEntryToEdit")}
                </Flex>
              )}
            </div>
          </Flex>
        )}

        {isMobile && (
          <>
            <motion.div
              initial={false}
              animate={{ opacity: mobileEntriesOpen ? 1 : 0 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              className="prompt-chains-page-mobile-sidebar-backdrop"
              onClick={() => setMobileEntriesOpen(false)}
              style={{ pointerEvents: mobileEntriesOpen ? "auto" : "none" }}
            />

            <MotionBox
              initial={false}
              animate={{ x: mobileEntriesOpen ? 0 : -320 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              className="prompt-chains-page-mobile-sidebar-overlay"
              style={{ pointerEvents: mobileEntriesOpen ? "auto" : "none" }}
            >
              <Box className="prompt-chains-page-mobile-sidebar-sheet">{sidebarContent}</Box>
            </MotionBox>
          </>
        )}
      </Box>

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={!!deletingEntryId}
        onOpenChange={(open) => !open && setDeletingEntryId(null)}
        onConfirm={confirmDeleteEntry}
        title={t("promptChains.confirmDelete")}
        description={t("promptChains.deleteEntryConfirm")}
        confirmText={t("promptChains.deleteButton")}
        cancelText={t("promptChains.cancelButton")}
        confirmColor="red"
      />

      {/* 编译结果弹窗 */}
      <PromptChainDialog
        open={compileDialogOpen}
        onOpenChange={setCompileDialogOpen}
        entries={compileResult?.entries ?? []}
        isLoading={isCompiling}
        title={t("promptChains.compileResult")}
        description={
          compileResult
            ? t("promptChains.compileResultDescription", {
                count: compileResult.entries.length,
                tokens: compileResult.total_tokens,
              })
            : undefined
        }
      />
    </Box>
  );
}
