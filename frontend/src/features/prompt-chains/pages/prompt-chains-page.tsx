/**
 * PromptChainsPage Component
 *
 * Halaman pengelolaan rantai prompt.
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

import { ConfirmDialog, PanelLayoutLoading, PromptChainDialog } from "@/components";
import { MobileAppSidebarTrigger, useAppShell } from "@/features/app-shell";
import { useMobileSidebarSwipe } from "@/hooks/use-mobile-sidebar-swipe";
import { usePersistedPanelLayout } from "@/hooks/use-persisted-panel-layout";
import { fetchPromptChainsMetadata, compilePromptChain, resetPromptChain } from "@/lib/api-client";
import type { PromptEntryData, CompileResponse } from "@/lib/prompt-chain.types";
import type { PromptChainsMetadata } from "@/lib/prompt-chain.types";

import { EntriesSidebar } from "../components/entries-sidebar";
import { PromptEditor } from "../components/prompt-editor";
import { VersionHistorySidebar } from "../components/version-history-sidebar";
import { usePromptChain } from "../hooks/use-prompt-chain";

const DEFAULT_PROMPT_ID = "builtin-agent--explore";
const VERSION_HISTORY_COLLAPSED_SIZE = 36;
const VERSION_HISTORY_MIN_SIZE = 72;
const PANEL_LAYOUT_KEY = "panel-layout.prompt-chains";
const PANEL_IDS = ["left-sidebar", "editor"];

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

  // Status metadata
  const [metadata, setMetadata] = useState<PromptChainsMetadata | null>(null);

  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(initialPromptId);

  // ID entri yang sedang disunting
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);

  // ID entri yang akan dihapus
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);

  // ID entri yang disorot (dipakai untuk animasi kedip setelah pembuatan)
  const [highlightEntryId, setHighlightEntryId] = useState<string | null>(null);

  // Status terkait kompilasi
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);
  const [compileDialogOpen, setCompileDialogOpen] = useState(false);

  // Status terkait pengaturan ulang
  const [isResetting, setIsResetting] = useState(false);

  const { isMobile } = useAppShell();
  const [mobileEntriesOpen, setMobileEntriesOpen] = useState(false);
  const mobileSidebarSwipeRef = useMobileSidebarSwipe({
    isEnabled: isMobile,
    isOpen: mobileEntriesOpen,
    onOpen: () => setMobileEntriesOpen(true),
    onClose: () => setMobileEntriesOpen(false),
  });
  const [isVersionHistoryCollapsed, setIsVersionHistoryCollapsed] = useState(false);
  const versionHistoryPanelRef = useRef<PanelImperativeHandle | null>(null);
  const panelLayout = usePersistedPanelLayout(PANEL_LAYOUT_KEY, PANEL_IDS, !isMobile);

  // Memuat metadata
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

  // Mengambil entri yang sedang dipilih (jika belum ada pilihan dan entri tersedia, pilih yang pertama otomatis)
  const actualSelectedId: string | null =
    selectedEntryId || (entries.length > 0 ? entries[0].id || null : null);
  const selectedEntry = entries.find((e) => e.id === actualSelectedId) || null;

  // Memperbarui entri (dioptimalkan memakai useCallback)
  const handleUpdateEntry = useCallback(
    (entryId: string, updates: Partial<PromptEntryData>) => {
      setEntries((prev) => {
        // Memeriksa adanya perubahan nyata, mencegah pembangunan ulang array yang tidak perlu
        const entry = prev.find((e) => e.id === entryId);
        if (!entry) return prev;

        // Memeriksa adanya perubahan nyata
        const hasChanges = Object.keys(updates).some(
          (key) => entry[key as keyof PromptEntryData] !== updates[key as keyof PromptEntryData],
        );

        if (!hasChanges) return prev;

        // Array baru hanya dibuat bila ada perubahan
        return prev.map((e) => (e.id === entryId ? { ...e, ...updates } : e));
      });
    },
    [setEntries],
  );

  // Mengalihkan status aktif entri (dioptimalkan memakai useCallback)
  const handleToggleEntry = useCallback(
    (entryId: string) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === entryId ? { ...e, is_enabled: !e.is_enabled } : e)),
      );
    },
    [setEntries],
  );

  // Menghapus entri (setelah dikonfirmasi)
  const confirmDeleteEntry = () => {
    if (deletingEntryId) {
      setEntries((prev) => prev.filter((e) => e.id !== deletingEntryId));
      // Jika yang dihapus adalah entri terpilih, bersihkan pilihannya
      if (deletingEntryId === selectedEntryId) {
        setSelectedEntryId(null);
      }
      setDeletingEntryId(null);
    }
  };

  // Membuat entri baru
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

    // Menyetel animasi sorotan
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

  // Mengompilasi rantai prompt
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

  // Mengembalikan ke bawaan
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
    <Box
      {...mobileSidebarSwipeRef}
      className="prompt-chains-page-root mobile-sidebar-swipe-surface"
    >
      {/* Area isi utama - resizable panels */}
      <Box className="prompt-chains-page-main">
        {!isMobile && panelLayout.isLoaded ? (
          <Group
            orientation="horizontal"
            className="prompt-chains-page-group"
            defaultLayout={panelLayout.defaultLayout}
            onLayoutChanged={panelLayout.onLayoutChanged}
          >
            {/* Bilah sisi kiri: daftar entri */}
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

            {/* Kolom tengah: editor */}
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
        ) : isMobile ? (
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
        ) : (
          <PanelLayoutLoading />
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

            <Box
              className="mobile-sidebar-sheet prompt-chains-page-mobile-sidebar-overlay"
              data-open={String(mobileEntriesOpen)}
            >
              <Box className="prompt-chains-page-mobile-sidebar-sheet">{sidebarContent}</Box>
            </Box>
          </>
        )}
      </Box>

      {/* Dialog konfirmasi penghapusan */}
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

      {/* Dialog hasil kompilasi */}
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
