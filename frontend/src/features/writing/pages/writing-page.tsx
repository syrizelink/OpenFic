import { Box, Flex, IconButton, Tooltip } from "@radix-ui/themes";
import { Bot, List } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Panel, Group, Separator } from "react-resizable-panels";
import { useParams } from "react-router";

import "./writing-page.css";

import { MobileAppSidebarTrigger } from "@/features/app-shell";
import { AssistantSidebar } from "@/features/assistant";
import type { AssistantSidebarHandle, AssistantSidebarState } from "@/features/assistant";
import { getLastChapterId, setLastChapterId } from "@/lib/local-db";

import { ChapterEditor } from "../components/chapter-editor";
import { EditorTabs, EmptyTabContent } from "../components/editor-tabs";
import { NoteEditor } from "../components/note-editor";
import { PageLoadingOverlay } from "../components/page-loading-overlay";
import { WritingSidebar } from "../components/writing-sidebar";
import { useCreateChapter } from "../hooks/use-chapters";
import { useNoteTree } from "../hooks/use-notes";
import { useCreateVolume, useVolumeTree } from "../hooks/use-volumes";
import { isEmptyTab } from "../lib/tab.types";
import { useTabsStore, useActiveTabId, useTabs, useTabsLoaded } from "../store/use-tabs-store";
import { useWritingStore } from "../store/use-writing-store";

const MotionBox = motion.create(Box);
const MOBILE_SIDEBAR_WIDTH = 320;

export function WritingPage() {
  const { t } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();

  const { setCurrentChapter, hydrateSidebarView } = useWritingStore();
  const {
    openTab,
    openSingleTab,
    syncTabsWithChapters,
    syncTabs,
    closeAllTabs,
    showEmptyTab,
    setCurrentProject,
  } = useTabsStore();
  const activeTabId = useActiveTabId();
  const tabs = useTabs();
  const isTabsLoaded = useTabsLoaded();

  const activeTab = useMemo(() => tabs.find((t) => t.id === activeTabId), [tabs, activeTabId]);
  const activeRefId = useMemo(() => activeTab?.refId ?? null, [activeTab]);
  const activeType = useMemo(() => activeTab?.type ?? "chapter", [activeTab]);

  const currentChapterId = useMemo(
    () => (activeTab?.type === "chapter" ? activeTab.refId : null),
    [activeTab],
  );

  const createMutation = useCreateChapter(projectId ?? "");
  const createVolumeMutation = useCreateVolume(projectId ?? "");

  const { data: chaptersData, isLoading: isChaptersLoading } = useVolumeTree(projectId ?? "");

  const { data: noteTreeData } = useNoteTree(projectId ?? "");

  const isPageLoading = !isTabsLoaded || isChaptersLoading;

  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [assistantState, setAssistantState] = useState<AssistantSidebarState>({
    agentStatus: "idle",
    isAgentRunning: false,
  });
  const assistantSidebarRef = useRef<AssistantSidebarHandle | null>(null);

  const isAgentLocked = useMemo(
    () => assistantState.isAgentRunning,
    [assistantState.isAgentRunning],
  );
  const isViewingSubagent = assistantState.conversationDescriptor?.kind === "subagent";

  useEffect(() => {
    void hydrateSidebarView();
  }, [hydrateSidebarView]);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const allChapters = useMemo(
    () => chaptersData?.volumes.flatMap((volume) => volume.chapters) ?? [],
    [chaptersData],
  );

  const allNotes = useMemo(() => {
    if (!noteTreeData) return [];
    const notes: { id: string; title: string }[] = [];
    const walk = (categories: typeof noteTreeData.categories) => {
      for (const cat of categories) {
        for (const n of cat.notes) {
          notes.push({ id: n.id, title: n.title });
        }
        walk(cat.categories);
      }
    };
    walk(noteTreeData.categories);
    for (const n of noteTreeData.rootNotes) {
      notes.push({ id: n.id, title: n.title });
    }
    return notes;
  }, [noteTreeData]);

  const hasInitialized = useRef(false);
  const initialChapterNavigationSequenceRef = useRef(0);
  const prevProjectIdRef = useRef<string | null>(null);
  const [initialCurrentChapterNavigationKey, setInitialCurrentChapterNavigationKey] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (!projectId) return;

    if (prevProjectIdRef.current !== projectId) {
      hasInitialized.current = false;
      prevProjectIdRef.current = projectId;
      initialChapterNavigationSequenceRef.current += 1;
      setInitialCurrentChapterNavigationKey(
        `${projectId}:${initialChapterNavigationSequenceRef.current}`,
      );
    }

    const loadProject = async () => {
      await setCurrentProject(projectId);
    };

    loadProject();
  }, [projectId, setCurrentProject]);

  useEffect(() => {
    if (!isTabsLoaded || isChaptersLoading || !chaptersData) return;
    syncTabsWithChapters(allChapters);
  }, [allChapters, chaptersData, isChaptersLoading, syncTabsWithChapters, isTabsLoaded]);

  useEffect(() => {
    if (!isTabsLoaded || !noteTreeData) return;
    syncTabs(allNotes, "note");
  }, [allNotes, noteTreeData, syncTabs, isTabsLoaded]);

  useEffect(() => {
    if (!isMobile || !isTabsLoaded || tabs.length <= 1) return;

    const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? tabs[0];
    if (activeTab.refId) {
      openSingleTab(activeTab.refId, activeTab.title, activeTab.type);
    } else {
      closeAllTabs();
    }
  }, [activeTabId, closeAllTabs, isMobile, isTabsLoaded, openSingleTab, tabs]);

  useEffect(() => {
    if (!projectId || !isTabsLoaded || hasInitialized.current) return;

    const loadLastChapter = async () => {
      if (tabs.length > 0) {
        if (!activeTabId || isEmptyTab(activeTabId)) {
          setInitialCurrentChapterNavigationKey(null);
        }
        hasInitialized.current = true;
        return;
      }

      const lastChapterId = await getLastChapterId(projectId);
      if (lastChapterId) {
        const chapter = allChapters.find((c) => c.id === lastChapterId);
        if (chapter) {
          if (isMobile) {
            openSingleTab(lastChapterId, chapter.title);
          } else {
            openTab(lastChapterId, chapter.title);
          }
          hasInitialized.current = true;
          return;
        }
      }

      if (isMobile && allChapters.length > 0) {
        const firstChapter = allChapters[0];
        openSingleTab(firstChapter.id, firstChapter.title);
        hasInitialized.current = true;
        return;
      }

      setInitialCurrentChapterNavigationKey(null);
      hasInitialized.current = true;
    };

    loadLastChapter();
  }, [
    activeTabId,
    allChapters,
    isMobile,
    isTabsLoaded,
    openSingleTab,
    openTab,
    projectId,
    tabs.length,
  ]);

  useEffect(() => {
    if (projectId && activeTabId) {
      setLastChapterId(projectId, activeTabId);
    }
  }, [projectId, activeTabId]);

  useEffect(() => {
    setCurrentChapter(currentChapterId);
  }, [currentChapterId, setCurrentChapter]);

  useEffect(() => {
    if (!isMobile || !currentChapterId) return;

    const frameId = window.requestAnimationFrame(() => {
      const activeElement = document.activeElement;
      if (!(activeElement instanceof HTMLElement)) return;

      const isTextInput =
        activeElement instanceof HTMLInputElement || activeElement instanceof HTMLTextAreaElement;

      // Mobile browsers may restore editor/title focus after chapter navigation.
      if (!isTextInput && !activeElement.isContentEditable) return;

      activeElement.blur();
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [currentChapterId, isMobile]);

  const handleSelectItem = useCallback(
    (refId: string, title: string, type: "chapter" | "note" = "chapter") => {
      if (isMobile) {
        openSingleTab(refId, title, type);
        setIsSidebarOpen(false);
        return;
      }

      openTab(refId, title, type);
    },
    [openSingleTab, openTab, isMobile],
  );

  const handleChapterSelect = useCallback(
    (chapterId: string, chapterTitle: string) => {
      handleSelectItem(chapterId, chapterTitle, "chapter");
    },
    [handleSelectItem],
  );

  const handleNoteSelect = useCallback(
    (noteId: string, noteTitle: string) => {
      handleSelectItem(noteId, noteTitle, "note");
    },
    [handleSelectItem],
  );

  const handleShowEmptyTab = useCallback(() => {
    showEmptyTab();
  }, [showEmptyTab]);

  const handleCreateNewChapter = useCallback(async () => {
    try {
      let targetVolumeId = chaptersData?.volumes.at(-1)?.id;
      if (!targetVolumeId) {
        const volume = await createVolumeMutation.mutateAsync({
          title: t("writing.firstVolumeDefaultTitle"),
        });
        targetVolumeId = volume.id;
      }
      const newChapter = await createMutation.mutateAsync({
        volumeId: targetVolumeId,
        title: t("writing.untitledChapter"),
      });
      if (isMobile) {
        openSingleTab(newChapter.id, newChapter.title);
      } else {
        openTab(newChapter.id, newChapter.title);
      }
    } catch {
      // 错误处理由 mutation 处理
    }
  }, [
    chaptersData?.volumes,
    createMutation,
    createVolumeMutation,
    isMobile,
    t,
    openSingleTab,
    openTab,
  ]);

  const handleCloseAllTabs = useCallback(() => {
    closeAllTabs();
  }, [closeAllTabs]);

  const handleAddToConversation = useCallback(
    (markup: string) => {
      if (!markup.trim()) return;

      if (isMobile && !isAssistantOpen) {
        setIsAssistantOpen(true);
        window.requestAnimationFrame(() => {
          assistantSidebarRef.current?.appendToComposer(markup);
        });
        return;
      }

      assistantSidebarRef.current?.appendToComposer(markup);
    },
    [isAssistantOpen, isMobile],
  );

  if (!projectId) {
    return null;
  }

  const sidebarContent = (
    <WritingSidebar
      projectId={projectId}
      onChapterSelect={handleChapterSelect}
      onNoteSelect={handleNoteSelect}
      isAgentLocked={isAgentLocked}
      onAddToConversation={isViewingSubagent ? undefined : handleAddToConversation}
      initialCurrentChapterNavigationKey={initialCurrentChapterNavigationKey}
    />
  );

  return (
    <Box className="writing-page-root">
      <PageLoadingOverlay isLoading={isPageLoading} />

      <Box className="writing-page-shell">
        {!isMobile ? (
          <Group
            orientation="horizontal"
            className="writing-page-group"
          >
            <Panel
              id="left-sidebar"
              defaultSize={300}
              minSize={250}
              maxSize={400}
              collapsible={false}
            >
              <Box className="writing-page-sidebar writing-page-sidebar--left">
                {sidebarContent}
              </Box>
            </Panel>

            <Separator className="resize-handle writing-page-separator" />

            <Panel
              id="editor"
              minSize={30}
            >
              <div className="writing-page-editor-shell">
                <EditorTabs
                  onAddTab={handleShowEmptyTab}
                  onAddToConversation={isViewingSubagent ? undefined : handleAddToConversation}
                />

                <Box className="writing-page-content-fill">
                  {activeTabId && !isEmptyTab(activeTabId) ? (
                    activeType === "note" ? (
                      <NoteEditor
                        noteId={activeRefId}
                        projectId={projectId}
                        isAgentLocked={isAgentLocked}
                      />
                    ) : (
                      <ChapterEditor
                        chapterId={activeRefId}
                        projectId={projectId}
                        isAgentLocked={isAgentLocked}
                        onAddToConversation={
                          isViewingSubagent ? undefined : handleAddToConversation
                        }
                      />
                    )
                  ) : (
                    <EmptyTabContent
                      onCreateNew={handleCreateNewChapter}
                      onClose={handleCloseAllTabs}
                    />
                  )}
                </Box>
              </div>
            </Panel>

            <Separator className="resize-handle writing-page-separator" />

            <Panel
              id="right-sidebar"
              defaultSize={500}
              minSize={300}
              maxSize={600}
              collapsible={false}
            >
              <Box className="writing-page-sidebar writing-page-sidebar--right">
                <AssistantSidebar
                  ref={assistantSidebarRef}
                  projectId={projectId}
                  onStateChange={setAssistantState}
                  onOpenMentionChapter={handleChapterSelect}
                />
              </Box>
            </Panel>
          </Group>
        ) : (
          <Flex className="writing-page-mobile-layout">
            <div className="writing-page-editor-shell writing-page-editor-shell--mobile">
              <Flex
                align="center"
                justify="between"
                px="3"
                py="2"
                className="writing-page-mobile-topbar"
              >
                <Flex
                  align="center"
                  gap="1"
                >
                  <MobileAppSidebarTrigger />
                  <Tooltip content={t("writing.chapters")}>
                    <IconButton
                      variant="ghost"
                      size="2"
                      aria-label={t("writing.chapters")}
                      onClick={() => setIsSidebarOpen((open) => !open)}
                    >
                      <List size={18} />
                    </IconButton>
                  </Tooltip>
                </Flex>

                <Tooltip content={t("assistant.mobileTitle")}>
                  <IconButton
                    variant="ghost"
                    size="2"
                    aria-label={t("assistant.mobileTitle")}
                    onClick={() => setIsAssistantOpen(true)}
                  >
                    <Bot size={18} />
                  </IconButton>
                </Tooltip>
              </Flex>

              <Box className="writing-page-content-fill">
                {activeTabId && !isEmptyTab(activeTabId) ? (
                  activeType === "note" ? (
                    <NoteEditor
                      noteId={activeRefId}
                      projectId={projectId}
                      isAgentLocked={isAgentLocked}
                    />
                  ) : (
                    <ChapterEditor
                      chapterId={activeRefId}
                      projectId={projectId}
                      isAgentLocked={isAgentLocked}
                    />
                  )
                ) : (
                  <EmptyTabContent
                    onCreateNew={handleCreateNewChapter}
                    onClose={handleCloseAllTabs}
                  />
                )}
              </Box>

              <motion.div
                initial={false}
                animate={{ opacity: isSidebarOpen ? 1 : 0 }}
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                onClick={() => setIsSidebarOpen(false)}
                className="writing-page-mobile-sidebar-backdrop"
                style={{ pointerEvents: isSidebarOpen ? "auto" : "none" }}
              />

              <MotionBox
                initial={false}
                animate={{
                  x: isSidebarOpen ? 0 : -MOBILE_SIDEBAR_WIDTH,
                }}
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                className="writing-page-mobile-sidebar-sheet"
                style={{
                  width: MOBILE_SIDEBAR_WIDTH,
                  minWidth: MOBILE_SIDEBAR_WIDTH,
                  pointerEvents: isSidebarOpen ? "auto" : "none",
                }}
              >
                <WritingSidebar
                  projectId={projectId}
                  onChapterSelect={handleChapterSelect}
                  onNoteSelect={handleNoteSelect}
                  isAgentLocked={isAgentLocked}
                  onAddToConversation={isViewingSubagent ? undefined : handleAddToConversation}
                  compact
                  initialCurrentChapterNavigationKey={initialCurrentChapterNavigationKey}
                />
              </MotionBox>
            </div>
          </Flex>
        )}
      </Box>

      {isMobile && (
        <MotionBox
          initial={false}
          animate={{ x: isAssistantOpen ? 0 : "100%" }}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          className="writing-page-mobile-assistant-overlay"
          data-open={isAssistantOpen}
          aria-hidden={!isAssistantOpen}
        >
          <AssistantSidebar
            ref={assistantSidebarRef}
            projectId={projectId}
            onStateChange={setAssistantState}
            onOpenMentionChapter={handleChapterSelect}
            onClose={() => setIsAssistantOpen(false)}
            isMobileOverlay
          />
        </MotionBox>
      )}
    </Box>
  );
}
