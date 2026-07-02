/**
 * PromptChainsPage Component
 *
 * 提示词链管理页面 - 三栏布局（左：条目列表，中：编辑器，右：预留）
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { Box, Flex, IconButton, Tooltip } from "@radix-ui/themes";
import { Panel, Group, Separator } from "react-resizable-panels";
import { useTranslation } from "react-i18next";
import { List } from "lucide-react";
import { motion } from "motion/react";
import { useSearchParams } from "react-router";
import { v4 as uuidv4 } from "uuid";
import "./prompt-chains-page.css";
import { ConfirmDialog, PromptChainDialog } from "@/components";
import { MobileAppSidebarTrigger } from "@/features/app-shell";
import { PromptChainsTopBar } from "../components/prompt-chains-top-bar";
import { EntriesSidebar } from "../components/entries-sidebar";
import { PromptEditor } from "../components/prompt-editor";
import { MacroSidebar } from "../components/macro-sidebar";
import { usePromptChain } from "../hooks/use-prompt-chain";
import { usePromptChainStore } from "../store/use-prompt-chain-store";
import { fetchPromptChainsMetadata, compilePromptChain, resetPromptChain } from "@/lib/api-client";
import { findMacros, tryParseMacro } from "@/lib/macro";
import type { PromptEntryData, CompileResponse } from "@/lib/prompt-chain.types";
import type { PromptChainsMetadata } from "@/lib/prompt-chain.types";
import type { MacroNode } from "@/lib/macro";
import type { Editor } from "@tiptap/react";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

const MotionBox = motion.create(Box);

const DEFAULT_PROMPT_MODE = "assistant";
const DEFAULT_PROMPT_TASK = "agent";
const DEFAULT_PROMPT_AGENT = "explorer";

function getInitialPromptSelection(searchParams: URLSearchParams): {
  mode: string | null;
  task: string | null;
  agent: string | null;
} {
  const mode = searchParams.get("mode");
  const task = searchParams.get("task");
  if (!mode || !task) {
    return {
      mode: DEFAULT_PROMPT_MODE,
      task: DEFAULT_PROMPT_TASK,
      agent: DEFAULT_PROMPT_AGENT,
    };
  }

  return {
    mode,
    task,
    agent: searchParams.get("agent"),
  };
}

function getDefaultPromptChainSelection(metadata: PromptChainsMetadata): {
  mode: string | null;
  task: string | null;
  agent: string | null;
} {
  const preferredMode = metadata.modes.find((mode) => mode.value === DEFAULT_PROMPT_MODE);
  const preferredTask = preferredMode?.tasks.find((task) => task.value === DEFAULT_PROMPT_TASK);
  const preferredAgent = preferredTask?.agents.find((agent) => agent.value === DEFAULT_PROMPT_AGENT);
  if (preferredMode && preferredTask && preferredAgent) {
    return {
      mode: preferredMode.value,
      task: preferredTask.value,
      agent: preferredAgent.value,
    };
  }

  for (const mode of metadata.modes) {
    for (const task of mode.tasks) {
      const firstAgent = task.agents[0];
      if (firstAgent) {
        return {
          mode: mode.value,
          task: task.value,
          agent: firstAgent.value,
        };
      }
    }
  }

  const firstMode = metadata.modes[0];
  const firstTask = firstMode?.tasks[0];
  return {
    mode: firstMode?.value ?? null,
    task: firstTask?.value ?? null,
    agent: null,
  };
}

function getEffectivePromptChainSelection(
  metadata: PromptChainsMetadata | null,
  mode: string | null,
  task: string | null,
  agent: string | null
): {
  mode: string | null;
  task: string | null;
  agent: string | null;
} {
  if (!metadata) {
    return { mode, task, agent };
  }

  const matchedMode = metadata.modes.find((item) => item.value === mode);

  if (!matchedMode) {
    return getDefaultPromptChainSelection(metadata);
  }

  if (!task) {
    return {
      mode: matchedMode.value,
      task: null,
      agent: null,
    };
  }

  const matchedTask = matchedMode.tasks.find((item) => item.value === task);
  if (!matchedTask) {
    return {
      mode: matchedMode.value,
      task: null,
      agent: null,
    };
  }

  const needsAgent = matchedTask.agents.length > 0;
  if (!needsAgent) {
    return {
      mode: matchedMode.value,
      task: matchedTask.value,
      agent: null,
    };
  }

  const matchedAgent = matchedTask.agents.find((item) => item.value === agent);
  return {
    mode: matchedMode.value,
    task: matchedTask.value,
    agent: matchedAgent?.value ?? null,
  };
}

export function PromptChainsPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const initialSelection = getInitialPromptSelection(searchParams);
  
  // 元数据状态
  const [metadata, setMetadata] = useState<PromptChainsMetadata | null>(null);
  
  // 导航状态（使用ID，默认选中 assistant / agent / explorer）
  const [selectedMode, setSelectedMode] = useState<string | null>(initialSelection.mode);
  const [selectedTask, setSelectedTask] = useState<string | null>(initialSelection.task);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(initialSelection.agent);

  // 当前编辑的条目ID
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);

  // 待删除的条目ID
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);

  // 高亮的条目ID（用于新建后的闪烁动画）
  const [highlightEntryId, setHighlightEntryId] = useState<string | null>(null);

  // 选中的宏（用于侧边栏编辑）
  const [selectedMacro, setSelectedMacro] = useState<MacroNode | null>(null);

  // Work Dir store
  const { workDir, setWorkDir, loadWorkDirFromDB } = usePromptChainStore();

  // Editor ref for macro updates
  const editorRef = useRef<Editor | null>(null);
  const topBarRef = useRef<HTMLDivElement | null>(null);

  // 编译相关状态
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);
  const [compileDialogOpen, setCompileDialogOpen] = useState(false);

  // 重置相关状态
  const [isResetting, setIsResetting] = useState(false);

  // 响应式检测
  const [isMobile, setIsMobile] = useState(false);
  const [mobileEntriesOpen, setMobileEntriesOpen] = useState(false);
  const [mobileTopBarHeight, setMobileTopBarHeight] = useState(60);

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

  const effectiveSelection = getEffectivePromptChainSelection(
    metadata,
    selectedMode,
    selectedTask,
    selectedAgent
  );
  const effectiveSelectedMode = effectiveSelection.mode;
  const effectiveSelectedTask = effectiveSelection.task;
  const effectiveSelectedAgent = effectiveSelection.agent;

  // 加载缓存的工作目录设置
  useEffect(() => {
    loadWorkDirFromDB();
  }, [loadWorkDirFromDB]);

  // 从 metadata 中提取当前 mode+task 下是否有 agent 选项
  const hasAgentOptions = (() => {
    if (!effectiveSelectedMode || !effectiveSelectedTask || !metadata) return false;
    const mode = metadata.modes.find(m => m.value === effectiveSelectedMode);
    if (!mode) return false;
    const task = mode.tasks.find(tk => tk.value === effectiveSelectedTask);
    return !!task && task.agents.length > 0;
  })();

  useEffect(() => {
    if (!isMobile || !topBarRef.current) return;

    const element = topBarRef.current;

    const updateHeight = () => {
      setMobileTopBarHeight(element.getBoundingClientRect().height);
    };

    updateHeight();

    const observer = new ResizeObserver(updateHeight);
    observer.observe(element);
    window.addEventListener("resize", updateHeight);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateHeight);
    };
  }, [isMobile, effectiveSelectedMode, effectiveSelectedTask, effectiveSelectedAgent, hasAgentOptions]);

  // 使用自定义hook管理提示词链状态
  // 如果当前 task 有 agent 选项但尚未选择 agent，则不加载 chain（避免 404）
  const shouldLoadChain =
    effectiveSelectedMode &&
    effectiveSelectedTask &&
    (!hasAgentOptions || effectiveSelectedAgent);
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
  } = usePromptChain(
    shouldLoadChain ? effectiveSelectedMode : "",
    shouldLoadChain ? effectiveSelectedTask : "",
    effectiveSelectedAgent
  );

  // 获取当前选中的条目（如果没有选中且有条目，自动选择第一个）
  const actualSelectedId: string | null = selectedEntryId || (entries.length > 0 ? (entries[0].id || null) : null);
  const selectedEntry = entries.find((e) => e.id === actualSelectedId) || null;

  // 更新条目（使用 useCallback 优化）
  const handleUpdateEntry = useCallback((entryId: string, updates: Partial<PromptEntryData>) => {
    setEntries((prev) => {
      // 检查是否有实际变化，避免不必要的数组重建
      const entry = prev.find((e) => e.id === entryId);
      if (!entry) return prev;

      // 检查是否有实际变化
      const hasChanges = Object.keys(updates).some(
        (key) => entry[key as keyof PromptEntryData] !== updates[key as keyof PromptEntryData]
      );

      if (!hasChanges) return prev;

      // 有变化时才创建新数组
      return prev.map((e) => (e.id === entryId ? { ...e, ...updates } : e));
    });
  }, [setEntries]);

  // 切换条目启用状态（使用 useCallback 优化）
  const handleToggleEntry = useCallback((entryId: string) => {
    setEntries((prev) =>
      prev.map((e) =>
        e.id === entryId ? { ...e, is_enabled: !e.is_enabled } : e
      )
    );
  }, [setEntries]);

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

  const handleSelectEntry = useCallback((entryId: string) => {
    setSelectedEntryId(entryId);
    if (isMobile) {
      setMobileEntriesOpen(false);
    }
  }, [isMobile]);

  // 编译提示词链
  const handleCompile = useCallback(async () => {
    if (!effectiveSelectedMode || !effectiveSelectedTask) return;

    setIsCompiling(true);
    setCompileDialogOpen(true);
    setCompileResult(null);

    try {
      const result = await compilePromptChain(
        effectiveSelectedMode,
        effectiveSelectedTask,
        {
          project_id: workDir.projectId,
          // chapterId 为 null 表示使用最新章节
          chapter_id: workDir.chapterId || "latest",
        },
        effectiveSelectedAgent
      );
      setCompileResult(result);
    } catch (error) {
      console.error("Failed to compile prompt chain:", error);
    } finally {
      setIsCompiling(false);
    }
  }, [effectiveSelectedMode, effectiveSelectedTask, effectiveSelectedAgent, workDir]);

  // 重置到默认
  const handleReset = useCallback(async () => {
    if (!effectiveSelectedMode || !effectiveSelectedTask || isSaving) return;

    setIsResetting(true);
    try {
      const result = await resetPromptChain(
        effectiveSelectedMode,
        effectiveSelectedTask,
        effectiveSelectedAgent
      );
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
  }, [effectiveSelectedMode, effectiveSelectedTask, effectiveSelectedAgent, isSaving, resetWorkingCopy]);

  const handleSaveVersion = useCallback((note?: string) => {
    if (isResetting || !hasUnsavedChanges) return;

    saveVersion(note);
  }, [hasUnsavedChanges, isResetting, saveVersion]);

  // 更新宏内容
  const handleMacroUpdate = useCallback((newMacroRaw: string) => {
    const editor = editorRef.current;
    if (!editor || !selectedMacro) return;

    // 使用保存的宏位置进行查找和替换
    const { start, end } = selectedMacro;
    
    let foundPos = -1;
    let foundNode: ProseMirrorNode | null = null;

    editor.state.doc.nodesBetween(start, end, (node: ProseMirrorNode, pos) => {
      if (node.type.name === "macroNode") {
        foundPos = pos;
        foundNode = node;
        return false;
      }
    });

    if (foundPos !== -1 && foundNode) {
      const nodeToReplace = foundNode as ProseMirrorNode;

      // 解析新的宏
      const matches = findMacros(newMacroRaw);
      if (matches.length > 0) {
        const macroNode = tryParseMacro(matches[0]);
        if (macroNode) {
          // 保存当前 selection，防止触发 onSelectionUpdate 清除选中状态
          const prevSelection = editor.state.selection;
          
          const attrs = {
            macroName: macroNode.name,
            macroRaw: macroNode.raw,
            macroData: JSON.stringify({ args: macroNode.args }),
          };
          const tr = editor.state.tr;
          const newNode = editor.schema.nodes.macroNode.create(attrs);
          tr.replaceWith(foundPos, foundPos + nodeToReplace.nodeSize, newNode);
          // 恢复之前的 selection
          tr.setSelection(prevSelection);
          editor.view.dispatch(tr);
          
          // 更新选中的宏状态，保持同步
          setSelectedMacro({
            ...macroNode,
            start: foundPos,
            end: foundPos + newNode.nodeSize
          });
        }
      }
    }
  }, [selectedMacro]);

  const mobileEntrySidebarTrigger = isMobile ? (
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
  ) : null;

  return (
    <Box minHeight="100vh">
      <Box>
        {/* 页面顶栏：面包屑导航 + 版本选择器 + 保存按钮 */}
        <PromptChainsTopBar
          ref={topBarRef}
          leadingSlot={<MobileAppSidebarTrigger />}
          entrySidebarTrigger={mobileEntrySidebarTrigger}
          metadata={metadata}
          selectedMode={effectiveSelectedMode}
          selectedTask={effectiveSelectedTask}
          selectedAgent={effectiveSelectedAgent}
          onModeChange={setSelectedMode}
          onTaskChange={setSelectedTask}
          onAgentChange={setSelectedAgent}
          currentVersion={currentVersion}
          versions={versions}
          onVersionSelect={loadVersion}
          onSave={handleSaveVersion}
          onCompile={handleCompile}
          onReset={handleReset}
          isLoading={isLoading}
          isCompiling={isCompiling}
          isResetting={isResetting}
          isSaving={isSaving}
          hasUnsavedChanges={hasUnsavedChanges}
          isDefault={isDefault}
          workDir={workDir}
          onWorkDirChange={(projectId, chapterId) => setWorkDir({ projectId, chapterId })}
          modeName={effectiveSelectedMode || ""}
          taskName={effectiveSelectedTask || ""}
          agentName={effectiveSelectedAgent}
          isMobile={isMobile}
        />

        {/* 主内容区 - resizable panels */}
        <Box
          className="prompt-chains-page-main"
          style={isMobile ? { height: `calc(100dvh - ${mobileTopBarHeight}px)` } : undefined}
        >
          {!isMobile ? (
            <Group orientation="horizontal" className="prompt-chains-page-group">
              {/* 左侧边栏：条目列表 */}
              <Panel 
                id="left-sidebar"
                defaultSize={300} 
                minSize={250} 
                maxSize={400} 
                collapsible={false}
              >
                <Box className="prompt-chains-page-panel-shell prompt-chains-page-panel-shell--left">
                  <EntriesSidebar
                    entries={shouldLoadChain ? entries : []}
                    selectedEntryId={actualSelectedId}
                    onSelectEntry={setSelectedEntryId}
                    onToggleEntry={handleToggleEntry}
                    onDeleteEntry={setDeletingEntryId}
                    onReorderEntries={setEntries}
                    onCreateEntry={handleCreateEntry}
                    highlightEntryId={highlightEntryId}
                  />
                </Box>
              </Panel>

              <Separator className="resize-handle writing-page-separator" />

              {/* 中间栏：编辑器 */}
              <Panel id="editor" minSize={30}>
                <div className="prompt-chains-page-editor-panel">
                  {!shouldLoadChain ? (
                    <Flex align="center" justify="center" className="prompt-chains-page-empty-state">
                      {t("promptChains.selectModeAndTask")}
                    </Flex>
                  ) : selectedEntry && selectedEntry.id ? (
                    <PromptEditor
                      entry={selectedEntry}
                      onUpdate={(updates) =>
                        handleUpdateEntry(selectedEntry.id!, updates)
                      }
                      onUpdateWithId={handleUpdateEntry}
                      onMacroSelect={setSelectedMacro}
                      editorRef={editorRef}
                      isMobile={false}
                    />
                  ) : (
                    <Flex align="center" justify="center" className="prompt-chains-page-empty-state">
                      {t("promptChains.selectEntryToEdit")}
                    </Flex>
                  )}
                </div>
              </Panel>

              <Separator className="resize-handle writing-page-separator" />

              {/* 右侧栏：宏编辑器 */}
              <Panel 
                id="right-sidebar"
                defaultSize={300} 
                minSize={250} 
                maxSize={500} 
                collapsible={false}
              >
                <Box className="prompt-chains-page-panel-shell prompt-chains-page-panel-shell--right">
                  <MacroSidebar
                    selectedMacro={selectedMacro}
                    workDir={workDir}
                    onMacroUpdate={handleMacroUpdate}
                  />
                </Box>
              </Panel>
            </Group>
          ) : (
            // 移动端/Legacy Layout (保持原样，但适配 container 宽度)
            <Flex className="prompt-chains-page-mobile-layout">
              <div className="prompt-chains-page-editor-panel">
                {!shouldLoadChain ? (
                  <Flex align="center" justify="center" className="prompt-chains-page-empty-state">
                    {t("promptChains.selectModeAndTask")}
                  </Flex>
                ) : selectedEntry && selectedEntry.id ? (
                  <PromptEditor
                    entry={selectedEntry}
                    onUpdate={(updates) =>
                      handleUpdateEntry(selectedEntry.id!, updates)
                    }
                    onUpdateWithId={handleUpdateEntry}
                    onMacroSelect={setSelectedMacro}
                    editorRef={editorRef}
                    isMobile={true}
                  />
                ) : (
                  <Flex align="center" justify="center" className="prompt-chains-page-empty-state">
                    {t("promptChains.selectEntryToEdit")}
                  </Flex>
                )}
              </div>

              {selectedMacro && (
                <Box className="prompt-chains-page-mobile-macro">
                  <MacroSidebar
                    selectedMacro={selectedMacro}
                    workDir={workDir}
                    onMacroUpdate={handleMacroUpdate}
                  />
                </Box>
              )}
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
                <Box className="prompt-chains-page-mobile-sidebar-sheet">
                  <EntriesSidebar
                    entries={shouldLoadChain ? entries : []}
                    selectedEntryId={actualSelectedId}
                    onSelectEntry={handleSelectEntry}
                    onToggleEntry={handleToggleEntry}
                    onDeleteEntry={setDeletingEntryId}
                    onReorderEntries={setEntries}
                    onCreateEntry={handleCreateEntry}
                    highlightEntryId={highlightEntryId}
                  />
                </Box>
              </MotionBox>
            </>
          )}
        </Box>
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
        description={compileResult ? t("promptChains.compileResultDescription", {
          count: compileResult.entries.length,
          tokens: compileResult.total_tokens,
        }) : undefined}
      />
    </Box>
  );
}
