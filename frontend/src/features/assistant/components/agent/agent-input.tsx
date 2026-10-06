import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUp,
  Brain,
  CloudUpload,
  ExternalLink,
  Plus,
  ShieldCheck,
  Square,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { PhotoProvider, PhotoView } from "react-photo-view";

import "react-photo-view/dist/react-photo-view.css";

import { ModelIdSelect, Spinner, type ModelIdSelectOption } from "@/components";
import { toast } from "@/components";
import { SimpleSelect, type SelectOption } from "@/components/select";
import { ProviderIcon } from "@/features/settings/lib/provider-icons";
import type { AgentPendingMessage, AgentSessionStatus, ReasoningEffort } from "@/lib/agent.types";
import { fetchAgentComposerItems } from "@/lib/api-client";
import type { AgentComposerItems } from "@/lib/command.types";
import { REASONING_EFFORT_OPTIONS } from "@/lib/reasoning-effort";

import { useAgentInputHistory } from "../../hooks/use-agent-input-history";
import {
  getAgentFiles,
  hasLeftAgentDropZone,
  isImageAttachment,
  modelAllowsAgentImages,
  type PendingAgentAttachment,
  validateAgentFiles,
} from "../../lib/agent-file-attachments";
import type { AgentInputHistoryDirection } from "../../lib/agent-input-history-state";
import { AgentAttachmentStrip } from "./agent-attachment-strip";
import { AgentComposerAddMenu } from "./agent-composer-add-menu";
import {
  AgentComposerEditor,
  type AgentComposerActions,
  type AgentComposerSuggestionItem,
  type AgentComposerSuggestionState,
} from "./agent-composer-editor";
import { AgentFileAttachmentCard } from "./agent-file-attachment-card";
import { AgentIndexStatusIndicator } from "./agent-index-status-indicator";
import { canSendAgentInput, getAgentInputBodyMode, isAgentInputLocked } from "./agent-input-state";
import { AgentMentionSuggestions } from "./agent-mention-suggestions";
import { AgentPendingMessageCard } from "./pending-message-card";

interface AgentInputProps {
  projectId: string;
  value: string;
  attachments: PendingAgentAttachment[];
  modelId: string;
  models: ModelIdSelectOption[];
  reasoningEffort?: ReasoningEffort;
  agentKey?: string;
  agentOptions: SelectOption[];
  isSending: boolean;
  disabled: boolean;
  isModelsLoading: boolean;
  modelsError: boolean;
  onChange: (value: string) => void;
  onAttachmentsChange: (attachments: PendingAgentAttachment[]) => void;
  onSend: () => void;
  onAbort: () => void;
  onModelChange: (modelId: string) => void;
  onReasoningEffortChange?: (reasoningEffort: ReasoningEffort) => void;
  onAgentChange?: (agentKey: string) => void;
  onGoToSettings: () => void;
  agentStatus?: AgentSessionStatus;
  pendingMessage?: AgentPendingMessage | null;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  toolApprovalBypassEnabled?: boolean;
  toolApprovalBypassDisabled?: boolean;
  onToggleToolApprovalBypass?: () => void;
  onCancelPendingMessage?: () => void;
  specialPanels?: ReactNode;
  forceSpecialPanels?: boolean;
  readOnly?: boolean;
  readOnlyMessage?: ReactNode;
  onUploadAttachments: (files: File[]) => Promise<void>;
  [ignoredModeSelectorProp: string]: unknown;
}

const MAX_TOOLBAR_COMPRESSION_LEVEL = 4;

export function AgentInput({
  projectId,
  value,
  attachments,
  modelId,
  models,
  reasoningEffort,
  agentKey,
  agentOptions,
  isSending,
  disabled,
  isModelsLoading,
  modelsError,
  onChange,
  onAttachmentsChange,
  onSend,
  onAbort,
  onModelChange,
  onReasoningEffortChange,
  onAgentChange,
  onGoToSettings,
  agentStatus,
  pendingMessage = null,
  onOpenMentionChapter,
  toolApprovalBypassEnabled = false,
  toolApprovalBypassDisabled = false,
  onToggleToolApprovalBypass,
  onCancelPendingMessage,
  specialPanels,
  forceSpecialPanels = false,
  readOnly = false,
  readOnlyMessage,
  onUploadAttachments,
}: AgentInputProps) {
  const { t } = useTranslation();
  const bodyMode = getAgentInputBodyMode(agentStatus, Boolean(specialPanels), forceSpecialPanels);
  const hasContent = value.trim().length > 0 || attachments.length > 0;
  const hasPendingMessage = pendingMessage !== null;
  const isComposerLocked = isAgentInputLocked({
    disabled,
    readOnly,
    hasPendingMessage,
  });
  const isProcessingAttachments =
    attachments.some((attachment) => attachment.status === "uploading") ||
    (isSending &&
      attachments.some((attachment) => attachment.file && !attachment.uploadedAttachment));
  const shouldAbort = isSending && !hasContent;
  const canSend = canSendAgentInput({
    hasContent,
    disabled: disabled || isProcessingAttachments,
    readOnly,
    hasPendingMessage,
    bodyMode,
  });
  const shouldShowPendingMessage = hasPendingMessage && bodyMode === "composer" && !readOnly;
  const buttonActive = shouldAbort || canSend;
  const inputContainerRef = useRef<HTMLDivElement>(null);
  const [pendingClearanceHeight, setPendingClearanceHeight] = useState(0);
  const [mentionSuggestions, setMentionSuggestions] = useState<AgentComposerSuggestionState | null>(
    null,
  );
  const [composerActions, setComposerActions] = useState<AgentComposerActions | null>(null);
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const toolbarCompressionLevelRef = useRef(0);
  const previousToolbarWidthRef = useRef<number | null>(null);
  const [toolbarCompressionLevel, setToolbarCompressionLevel] = useState(0);
  const addMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const imageFileInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const {
    data: composerItems,
    isError: isComposerItemsError,
    isFetching: isComposerItemsFetching,
  } = useQuery<AgentComposerItems>({
    queryKey: ["assistant-agent-composer-items", projectId],
    queryFn: () => fetchAgentComposerItems(projectId),
    enabled: isAddMenuOpen && projectId.trim().length > 0,
    staleTime: 30 * 1000,
  });
  const isAddMenuDisabled =
    disabled || readOnly || bodyMode !== "composer" || isComposerLocked || !composerActions;
  const {
    draft: persistedDraft,
    handleInputChange: handleHistoryInputChange,
    isDraftLoaded,
    navigate: navigateInputHistory,
    record: recordInputHistory,
  } = useAgentInputHistory(projectId);
  const historyValueRef = useRef<string | null>(null);
  const previousProjectIdRef = useRef(projectId);
  const selectedModel = useMemo(
    () => models.find((model) => model.value === modelId || model.id === modelId),
    [modelId, models],
  );
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const canAttachImages = modelAllowsAgentImages(
    selectedModel?.inputModalities,
    selectedModel?.isCatalogMatched === true,
  );
  const modelTriggerPrefix = selectedModel ? (
    selectedModel.providerIconPath ? (
      <ProviderIcon
        size={14}
        iconPath={selectedModel.providerIconPath}
      />
    ) : null
  ) : null;
  const shouldShowReasoningEffort = Boolean(selectedModel);
  const isReasoningCompact = toolbarCompressionLevel >= 1;
  const isModelCompact = toolbarCompressionLevel >= 2;
  const isAgentCompact = toolbarCompressionLevel >= 3;
  const isAgentSelectorCompact =
    isAgentCompact && agentOptions.length > 0 && Boolean(onAgentChange);
  const isIndexStatusHidden = toolbarCompressionLevel >= 4;
  const toolbarContentKey = [
    agentKey ?? "",
    agentOptions.length,
    buttonActive,
    isModelsLoading,
    models.length,
    modelsError,
    modelId,
    reasoningEffort ?? "",
    shouldShowReasoningEffort,
    toolApprovalBypassEnabled,
  ].join("|");
  useEffect(() => {
    if (previousProjectIdRef.current === projectId) return;
    previousProjectIdRef.current = projectId;
    historyValueRef.current = "";
    onChange("");
  }, [onChange, projectId]);

  useEffect(() => {
    if (!isDraftLoaded || !persistedDraft || value !== "") return;
    historyValueRef.current = persistedDraft;
    onChange(persistedDraft);
  }, [isDraftLoaded, onChange, persistedDraft, value]);

  useEffect(() => {
    if (!isDraftLoaded) return;
    if (historyValueRef.current === value) {
      historyValueRef.current = null;
      return;
    }
    historyValueRef.current = null;
    handleHistoryInputChange(value);
  }, [handleHistoryInputChange, isDraftLoaded, value]);

  const handleComposerChange = useCallback(
    (nextValue: string) => {
      historyValueRef.current = null;
      handleHistoryInputChange(nextValue);
      onChange(nextValue);
    },
    [handleHistoryInputChange, onChange],
  );

  const handleHistoryNavigate = useCallback(
    (direction: AgentInputHistoryDirection): boolean => {
      const nextValue = navigateInputHistory(direction, value);
      if (nextValue === null) return false;
      historyValueRef.current = nextValue;
      onChange(nextValue);
      return true;
    },
    [navigateInputHistory, onChange, value],
  );

  const handleSubmit = useCallback(() => {
    recordInputHistory(value);
    onSend();
  }, [onSend, recordInputHistory, value]);

  useLayoutEffect(() => {
    const container = inputContainerRef.current;
    if (!container) return;

    const syncHeight = () => {
      const nextHeight = Math.round(container.getBoundingClientRect().height);
      setPendingClearanceHeight((currentHeight) =>
        currentHeight === nextHeight ? currentHeight : nextHeight,
      );
    };

    syncHeight();

    if (typeof ResizeObserver === "undefined") return;

    const resizeObserver = new ResizeObserver(() => {
      syncHeight();
    });
    resizeObserver.observe(container);
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  const updateToolbarCompressionLevel = useCallback((nextLevel: number) => {
    const normalizedLevel = Math.max(0, Math.min(nextLevel, MAX_TOOLBAR_COMPRESSION_LEVEL));
    toolbarCompressionLevelRef.current = normalizedLevel;
    setToolbarCompressionLevel((currentLevel) =>
      currentLevel === normalizedLevel ? currentLevel : normalizedLevel,
    );
  }, []);

  useLayoutEffect(() => {
    const toolbar = toolbarRef.current;
    if (!toolbar) return;

    const syncOverflow = (allowExpand: boolean) => {
      const currentLevel = toolbarCompressionLevelRef.current;
      const currentWidth = toolbar.clientWidth;
      const previousWidth = previousToolbarWidthRef.current;
      const widthIncreased = previousWidth !== null && currentWidth > previousWidth + 1;
      const isOverflowing = toolbar.scrollWidth > currentWidth + 1;
      previousToolbarWidthRef.current = currentWidth;

      if (isOverflowing && currentLevel < MAX_TOOLBAR_COMPRESSION_LEVEL) {
        updateToolbarCompressionLevel(currentLevel + 1);
      } else if (allowExpand && widthIncreased && !isOverflowing && currentLevel > 0) {
        updateToolbarCompressionLevel(currentLevel - 1);
      }
    };

    syncOverflow(false);

    if (typeof ResizeObserver === "undefined") return;

    const resizeObserver = new ResizeObserver(() => syncOverflow(true));
    resizeObserver.observe(toolbar);
    return () => resizeObserver.disconnect();
  }, [toolbarCompressionLevel, toolbarContentKey, updateToolbarCompressionLevel]);

  useEffect(() => {
    if (bodyMode === "composer" && !readOnly && !isComposerLocked) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setMentionSuggestions(null);
    });
    return () => {
      cancelled = true;
    };
  }, [bodyMode, isComposerLocked, readOnly]);

  useEffect(() => {
    if (isAddMenuDisabled) setIsAddMenuOpen(false);
  }, [isAddMenuDisabled]);

  useEffect(() => {
    if (!isDraggingFiles) return;

    const clearDraggingFiles = () => setIsDraggingFiles(false);
    const preventFileDrop = (event: DragEvent) => {
      if (event.dataTransfer?.types.includes("Files")) event.preventDefault();
    };
    window.addEventListener("dragend", clearDraggingFiles);
    window.addEventListener("blur", clearDraggingFiles);
    window.addEventListener("dragover", preventFileDrop, true);
    window.addEventListener("drop", preventFileDrop, true);
    window.addEventListener("drop", clearDraggingFiles);
    return () => {
      window.removeEventListener("dragend", clearDraggingFiles);
      window.removeEventListener("blur", clearDraggingFiles);
      window.removeEventListener("dragover", preventFileDrop, true);
      window.removeEventListener("drop", preventFileDrop, true);
      window.removeEventListener("drop", clearDraggingFiles);
    };
  }, [isDraggingFiles]);

  const getPlaceholder = () => {
    if (agentStatus === "waiting_answer")
      return t("writing.aiSidebar.inputPlaceholderWaitingAnswer");
    if (agentStatus === "waiting_approval")
      return t("writing.aiSidebar.inputPlaceholderWaitingApproval");
    return t("writing.aiSidebar.inputPlaceholder");
  };

  const handleFiles = async (files: File[]) => {
    const validation = validateAgentFiles(files, attachments.length, canAttachImages);
    if (validation.rejectedFiles.length > 0) {
      toast.error(
        validation.validFiles.length > 0
          ? t("writing.aiSidebar.attachmentsSkipped", { count: validation.rejectedFiles.length })
          : (validation.errors[0] ?? t("writing.aiSidebar.unsupportedAttachmentType")),
      );
    }
    if (validation.validFiles.length > 0) await onUploadAttachments(validation.validFiles);
  };

  const handlePickFile = (kind: "image" | "file") => {
    setIsAddMenuOpen(false);
    const input = kind === "image" ? imageFileInputRef.current : fileInputRef.current;
    input?.click();
  };

  const handleFilePickerChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length > 0) void handleFiles(files);
  };

  const handleInsertTrigger = (trigger: "/" | "@") => {
    composerActions?.insertTrigger(trigger);
    setIsAddMenuOpen(false);
  };

  const handleSelectComposerItem = (item: AgentComposerSuggestionItem) => {
    composerActions?.insertCandidate(item);
    setIsAddMenuOpen(false);
  };

  const handleToggleAddMenu = () => {
    setIsAddMenuOpen((current) => {
      const next = !current;
      if (next) {
        mentionSuggestions?.onClose();
        setMentionSuggestions(null);
      }
      return next;
    });
  };

  const handleCloseAddMenu = () => setIsAddMenuOpen(false);

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDraggingFiles(false);
    const files = getAgentFiles(event.dataTransfer);
    if (files.length === 0) return;
    void handleFiles(files);
  };

  const handlePastedFiles = (dataTransfer: DataTransfer) => {
    const files = getAgentFiles(dataTransfer);
    if (files.length === 0) return;
    void handleFiles(files);
  };

  const handleDroppedFiles = (dataTransfer: DataTransfer) => {
    setIsDraggingFiles(false);
    handlePastedFiles(dataTransfer);
  };

  const handleRemoveAttachment = (id: string) => {
    const attachment = attachments.find((item) => item.id === id);
    if (attachment?.previewUrl.startsWith("blob:")) URL.revokeObjectURL(attachment.previewUrl);
    onAttachmentsChange(attachments.filter((item) => item.id !== id));
  };

  return (
    <Box className="ai-sidebar-input-area">
      <input
        ref={imageFileInputRef}
        className="agent-composer-file-input"
        type="file"
        accept="image/*"
        multiple
        onChange={handleFilePickerChange}
      />
      <input
        ref={fileInputRef}
        className="agent-composer-file-input"
        type="file"
        multiple
        onChange={handleFilePickerChange}
      />
      <div className="ai-sidebar-input-stage">
        <AnimatePresence initial={false}>
          {mentionSuggestions ? (
            <AgentMentionSuggestions
              key="mention-suggestions"
              clearanceHeight={pendingClearanceHeight}
              mode={mentionSuggestions.mode}
              items={mentionSuggestions.items}
              selectedIndex={mentionSuggestions.selectedIndex}
              status={mentionSuggestions.status}
              visible
              onSelect={mentionSuggestions.onSelect}
              onSelectedIndexChange={mentionSuggestions.onSelectedIndexChange}
              onClose={mentionSuggestions.onClose}
            />
          ) : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {isAddMenuOpen ? (
            <AgentComposerAddMenu
              key="composer-add-menu"
              clearanceHeight={pendingClearanceHeight}
              visible
              triggerRef={addMenuTriggerRef}
              items={composerItems ?? null}
              status={
                isComposerItemsError
                  ? "error"
                  : isComposerItemsFetching && !composerItems
                    ? "loading"
                    : "ready"
              }
              errorMessage={t("assistant.composerMenu.loadFailed")}
              onClose={handleCloseAddMenu}
              onPickFile={handlePickFile}
              onInsertTrigger={handleInsertTrigger}
              onSelectItem={handleSelectComposerItem}
            />
          ) : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {shouldShowPendingMessage ? (
            <AgentPendingMessageCard
              key={`pending-${pendingMessage!.messageId}`}
              pendingMessage={pendingMessage!}
              clearanceHeight={pendingClearanceHeight}
              onCancel={onCancelPendingMessage}
              onOpenMentionChapter={onOpenMentionChapter}
            />
          ) : null}
        </AnimatePresence>

        <div
          ref={inputContainerRef}
          className="ai-sidebar-input-container"
          data-mode={bodyMode}
          data-dragging-files={isDraggingFiles || undefined}
          onDragEnter={(event) => {
            if (event.dataTransfer.types.includes("Files")) setIsDraggingFiles(true);
          }}
          onDragOver={(event) => {
            if (!event.dataTransfer.types.includes("Files")) return;
            event.preventDefault();
            event.stopPropagation();
          }}
          onDragLeave={(event) => {
            if (
              hasLeftAgentDropZone(event.relatedTarget, (target) =>
                event.currentTarget.contains(target),
              )
            ) {
              setIsDraggingFiles(false);
            }
          }}
          onDrop={handleDrop}
        >
          <div
            className="agent-file-drop-overlay"
            aria-hidden="true"
          >
            <span className="agent-file-drop-overlay-content">
              <CloudUpload size={16} />
              {t("writing.aiSidebar.dropAttachments")}
            </span>
          </div>
          <AnimatePresence
            initial={false}
            mode="wait"
          >
            {bodyMode === "special_panels" ? (
              <motion.div
                key="special-panels"
                className="ai-sidebar-input-body"
                data-mode="special_panels"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
              >
                {specialPanels}
              </motion.div>
            ) : readOnly ? (
              <motion.div
                key="read-only"
                className="ai-sidebar-input-body"
                data-mode="read_only"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
              >
                <Box
                  style={{
                    padding: "12px 14px",
                    borderRadius: "10px",
                    background: "var(--gray-a3)",
                    color: "var(--gray-11)",
                    fontSize: "var(--font-size-sm)",
                    lineHeight: 1.5,
                  }}
                >
                  {readOnlyMessage}
                </Box>
              </motion.div>
            ) : (
              <motion.div
                key="composer"
                className="ai-sidebar-input-body"
                data-mode="composer"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
              >
                {attachments.length > 0 ? (
                  <PhotoProvider>
                    <AgentAttachmentStrip
                      className="agent-file-attachment-strip"
                      previousLabel={t("writing.aiSidebar.previousAttachment")}
                      nextLabel={t("writing.aiSidebar.nextAttachment")}
                    >
                      {attachments.map((attachment) => {
                        const fileName =
                          attachment.file?.name ??
                          attachment.uploadedAttachment?.fileName ??
                          t("writing.aiSidebar.attachmentFallbackName");
                        const isImage = attachment.file
                          ? attachment.file.type.startsWith("image/")
                          : attachment.uploadedAttachment
                            ? isImageAttachment(attachment.uploadedAttachment)
                            : false;
                        const isProcessing =
                          attachment.status === "uploading" ||
                          (isSending && Boolean(attachment.file && !attachment.uploadedAttachment));
                        const sizeBytes =
                          attachment.file?.size ?? attachment.uploadedAttachment?.sizeBytes ?? 0;
                        return (
                          <div
                            key={attachment.id}
                            className={
                              isImage
                                ? "agent-image-attachment-preview"
                                : "agent-file-attachment-item"
                            }
                          >
                            {isImage ? (
                              <>
                                <PhotoView src={attachment.previewUrl}>
                                  <button
                                    type="button"
                                    className="agent-image-preview-trigger"
                                    aria-label={t("writing.aiSidebar.viewImage", { fileName })}
                                  >
                                    <img
                                      src={attachment.previewUrl}
                                      alt={fileName}
                                    />
                                  </button>
                                </PhotoView>
                                <button
                                  type="button"
                                  className="agent-image-attachment-remove"
                                  aria-label={t("writing.aiSidebar.removeAttachment", { fileName })}
                                  onClick={() => handleRemoveAttachment(attachment.id)}
                                >
                                  <X size={12} />
                                </button>
                              </>
                            ) : (
                              <AgentFileAttachmentCard
                                fileName={fileName}
                                mimeType={
                                  attachment.file?.type ?? attachment.uploadedAttachment?.mimeType
                                }
                                sizeBytes={sizeBytes}
                                isProcessing={isProcessing}
                                removeLabel={t("writing.aiSidebar.removeAttachment", { fileName })}
                                extractingLabel={t("writing.aiSidebar.extractingAttachment")}
                                onRemove={() => handleRemoveAttachment(attachment.id)}
                              />
                            )}
                          </div>
                        );
                      })}
                    </AgentAttachmentStrip>
                  </PhotoProvider>
                ) : null}
                <AgentComposerEditor
                  projectId={projectId}
                  placeholder={getPlaceholder()}
                  value={value}
                  disabled={isComposerLocked}
                  onOpenMentionChapter={onOpenMentionChapter}
                  onMentionSuggestionsChange={setMentionSuggestions}
                  onComposerActionsChange={setComposerActions}
                  onPasteFiles={handlePastedFiles}
                  onDropFiles={handleDroppedFiles}
                  onChange={handleComposerChange}
                  onHistoryNavigate={handleHistoryNavigate}
                  onSubmit={handleSubmit}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {readOnly ? null : (
        <Flex
          ref={toolbarRef}
          justify="between"
          align="center"
          gap="2"
          className="ai-sidebar-input-toolbar"
        >
          <Flex
            align="center"
            gap={isAgentSelectorCompact ? "0" : "2"}
            wrap="nowrap"
            className="ai-sidebar-input-toolbar-controls"
          >
            <IconButton
              ref={addMenuTriggerRef}
              type="button"
              variant="ghost"
              size="1"
              className="agent-composer-add-trigger"
              disabled={isAddMenuDisabled}
              aria-label={t("assistant.composerMenu.open")}
              aria-expanded={isAddMenuOpen}
              onClick={handleToggleAddMenu}
            >
              <Plus size={16} />
            </IconButton>
            {isModelsLoading ? (
              <Flex
                align="center"
                gap="2"
                style={{ flex: "0 0 auto" }}
              >
                <Spinner size={18} />
                <Text
                  size="1"
                  color="gray"
                >
                  {t("common.loading")}
                </Text>
              </Flex>
            ) : models.length === 0 || modelsError ? (
              <Tooltip content={t("writing.aiSidebar.noModelsTooltip")}>
                <Flex
                  align="center"
                  gap="1"
                  className="ai-sidebar-no-models"
                >
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("writing.aiSidebar.noModelsMessage")}
                  </Text>
                  <button
                    type="button"
                    className="ai-sidebar-no-models-action"
                    onClick={onGoToSettings}
                  >
                    <Text
                      size="1"
                      className="ai-sidebar-no-models-action-text"
                    >
                      {t("writing.aiSidebar.noModelsAction")}
                    </Text>
                    <ExternalLink
                      size={12}
                      aria-hidden="true"
                    />
                  </button>
                </Flex>
              </Tooltip>
            ) : (
              <>
                {agentOptions.length > 0 && onAgentChange ? (
                  <Box className="ai-sidebar-model-selector ai-sidebar-agent-selector">
                    <SimpleSelect
                      value={agentKey ?? ""}
                      options={agentOptions}
                      onChange={onAgentChange}
                      size="1"
                      variant={isAgentSelectorCompact ? "icon" : "default"}
                      triggerAriaLabel={
                        agentOptions.find((option) => option.value === agentKey)?.label
                      }
                      hideTriggerChevron
                      contentClassName="ai-sidebar-agent-select-content"
                      triggerClassName="ai-sidebar-inline-select-trigger ai-sidebar-agent-select-trigger"
                      triggerStyle={{
                        fontSize: "var(--font-size-sm)",
                        border: "none",
                        background: "transparent",
                        boxShadow: "none",
                      }}
                    />
                  </Box>
                ) : null}
                <Flex
                  align="center"
                  gap={isModelCompact && isReasoningCompact ? "0" : "2"}
                  className="ai-sidebar-model-reasoning-group"
                >
                  <Box className="ai-sidebar-model-selector">
                    <ModelIdSelect
                      value={modelId}
                      models={models}
                      onChange={onModelChange}
                      editable={false}
                      allowCustomValue={false}
                      compact
                      compactTrigger={isModelCompact}
                      triggerPrefix={modelTriggerPrefix}
                      hideTriggerChevron
                      triggerClassName="ai-sidebar-inline-select-trigger"
                      triggerStyle={{
                        fontSize: "var(--font-size-sm)",
                        border: "none",
                        background: "transparent",
                        boxShadow: "none",
                      }}
                    />
                  </Box>
                  {shouldShowReasoningEffort && reasoningEffort && onReasoningEffortChange ? (
                    <Box
                      className={`ai-sidebar-reasoning-effort-selector${
                        isReasoningCompact ? " ai-sidebar-reasoning-effort-selector--compact" : ""
                      }`}
                    >
                      <SimpleSelect
                        value={reasoningEffort}
                        options={REASONING_EFFORT_OPTIONS}
                        onChange={(value) => onReasoningEffortChange(value as ReasoningEffort)}
                        size="1"
                        variant={isReasoningCompact ? "icon" : "default"}
                        triggerPrefix={isReasoningCompact ? <Brain size={14} /> : undefined}
                        triggerAriaLabel={t("assistant.thinkingTitle")}
                        hideTriggerChevron
                        triggerClassName="ai-sidebar-inline-select-trigger ai-sidebar-reasoning-effort-trigger"
                        triggerStyle={{
                          fontSize: "var(--font-size-sm)",
                          border: "none",
                          background: "transparent",
                          boxShadow: "none",
                        }}
                      />
                    </Box>
                  ) : null}
                </Flex>
              </>
            )}
          </Flex>

          <Flex
            align="center"
            gap="2"
            className="ai-sidebar-input-toolbar-actions"
          >
            {isIndexStatusHidden ? null : <AgentIndexStatusIndicator projectId={projectId} />}

            <Tooltip
              content={
                toolApprovalBypassEnabled
                  ? t("writing.aiSidebar.toolApprovalBypassOn")
                  : t("writing.aiSidebar.toolApprovalBypassOff")
              }
            >
              <IconButton
                type="button"
                variant="ghost"
                color={toolApprovalBypassEnabled ? "green" : "gray"}
                highContrast={!toolApprovalBypassEnabled}
                size="1"
                onClick={onToggleToolApprovalBypass}
                disabled={toolApprovalBypassDisabled}
                aria-pressed={toolApprovalBypassEnabled}
                aria-label={
                  toolApprovalBypassEnabled
                    ? t("writing.aiSidebar.toolApprovalBypassOn")
                    : t("writing.aiSidebar.toolApprovalBypassOff")
                }
                style={{
                  width: "26px",
                  height: "26px",
                  padding: 0,
                  borderRadius: "999px",
                  background: toolApprovalBypassEnabled ? "var(--green-a3)" : "transparent",
                  color: toolApprovalBypassEnabled ? "var(--green-11)" : undefined,
                  border: "none",
                }}
              >
                <ShieldCheck size={14} />
              </IconButton>
            </Tooltip>

            <motion.div
              animate={{
                opacity: buttonActive ? 1 : 0.2,
                scale: 1,
              }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              style={{ display: "flex" }}
            >
              <IconButton
                variant="solid"
                size="1"
                className="ai-sidebar-send-button"
                onClick={shouldAbort ? onAbort : handleSubmit}
                disabled={shouldAbort ? false : !canSend}
                aria-disabled={!buttonActive || undefined}
                style={{
                  width: "26px",
                  height: "26px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 0,
                  opacity: 1,
                  pointerEvents: buttonActive ? undefined : "none",
                }}
              >
                {shouldAbort ? (
                  <Square
                    size={12}
                    fill="currentColor"
                  />
                ) : disabled ? (
                  <Spinner size={18} />
                ) : (
                  <ArrowUp size={14} />
                )}
              </IconButton>
            </motion.div>
          </Flex>
        </Flex>
      )}
    </Box>
  );
}
