import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { ArrowUp, CloudUpload, ExternalLink, ShieldCheck, Square, X } from "lucide-react";
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

import { useAgentInputHistory } from "../../hooks/use-agent-input-history";
import {
  getAgentImageFiles,
  hasLeftAgentImageDropZone,
  modelAllowsAgentImages,
  type PendingAgentImageAttachment,
  validateAgentImageFiles,
} from "../../lib/agent-image-attachments";
import type { AgentInputHistoryDirection } from "../../lib/agent-input-history-state";
import { AgentComposerEditor, type AgentComposerSuggestionState } from "./agent-composer-editor";
import { AgentIndexStatusIndicator } from "./agent-index-status-indicator";
import { canSendAgentInput, getAgentInputBodyMode, isAgentInputLocked } from "./agent-input-state";
import { AgentMentionSuggestions } from "./agent-mention-suggestions";
import { AgentPendingMessageCard } from "./pending-message-card";

interface AgentInputProps {
  projectId: string;
  value: string;
  attachments: PendingAgentImageAttachment[];
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
  onAttachmentsChange: (attachments: PendingAgentImageAttachment[]) => void;
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
  const shouldAbort = isSending && !hasContent;
  const canSend = canSendAgentInput({
    hasContent,
    disabled,
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
  const [isDraggingImages, setIsDraggingImages] = useState(false);
  const canAttachImages = modelAllowsAgentImages(
    selectedModel?.inputModalities,
    selectedModel?.isCatalogMatched === true,
  );
  const modelTriggerPrefix = selectedModel ? (
    <ProviderIcon
      size={14}
      iconPath={selectedModel.providerIconPath}
    />
  ) : null;
  const shouldShowReasoningEffort = Boolean(selectedModel);
  const reasoningEffortOptions: SelectOption[] = [
    { value: "off", label: "Off" },
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "xhigh", label: "Xhigh" },
    { value: "max", label: "Max" },
  ];

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
    if (!isDraggingImages) return;

    const clearDraggingImages = () => setIsDraggingImages(false);
    window.addEventListener("dragend", clearDraggingImages);
    window.addEventListener("drop", clearDraggingImages);
    return () => {
      window.removeEventListener("dragend", clearDraggingImages);
      window.removeEventListener("drop", clearDraggingImages);
    };
  }, [isDraggingImages]);

  const getPlaceholder = () => {
    if (agentStatus === "waiting_answer")
      return t("writing.aiSidebar.inputPlaceholderWaitingAnswer");
    if (agentStatus === "waiting_approval")
      return t("writing.aiSidebar.inputPlaceholderWaitingApproval");
    return t("writing.aiSidebar.inputPlaceholder");
  };

  const handleFiles = async (files: File[]) => {
    const error = validateAgentImageFiles(files, attachments.length);
    if (error) {
      toast.error(error);
      return;
    }
    await onUploadAttachments(files);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    const files = getAgentImageFiles(event.dataTransfer);
    if (files.length === 0) return;
    event.preventDefault();
    setIsDraggingImages(false);
    if (!canAttachImages) {
      toast.error(t("writing.aiSidebar.modelImageInputUnsupported"));
      return;
    }
    void handleFiles(files);
  };

  const handlePastedFiles = (dataTransfer: DataTransfer) => {
    const files = getAgentImageFiles(dataTransfer);
    if (files.length === 0) return;
    if (!canAttachImages) {
      toast.error(t("writing.aiSidebar.modelImageInputUnsupported"));
      return;
    }
    void handleFiles(files);
  };

  const handleDroppedFiles = (dataTransfer: DataTransfer) => {
    setIsDraggingImages(false);
    handlePastedFiles(dataTransfer);
  };

  const handleRemoveAttachment = (id: string) => {
    const attachment = attachments.find((item) => item.id === id);
    if (attachment) URL.revokeObjectURL(attachment.previewUrl);
    onAttachmentsChange(attachments.filter((item) => item.id !== id));
  };

  return (
    <Box className="ai-sidebar-input-area">
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
          data-dragging-images={isDraggingImages || undefined}
          onDragEnter={(event) => {
            if (event.dataTransfer.types.includes("Files")) setIsDraggingImages(true);
          }}
          onDragOver={(event) => {
            if (getAgentImageFiles(event.dataTransfer).length > 0) event.preventDefault();
          }}
          onDragLeave={(event) => {
            if (
              hasLeftAgentImageDropZone(event.relatedTarget, (target) =>
                event.currentTarget.contains(target),
              )
            ) {
              setIsDraggingImages(false);
            }
          }}
          onDrop={handleDrop}
        >
          <div
            className="agent-image-drop-overlay"
            aria-hidden="true"
          >
            <span className="agent-image-drop-overlay-content">
              <CloudUpload size={16} />
              {t("writing.aiSidebar.dropImageAttachments")}
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
                    <div className="agent-image-attachment-strip">
                      {attachments.map((attachment) => {
                        const fileName =
                          attachment.file?.name ??
                          attachment.uploadedAttachment?.fileName ??
                          t("writing.aiSidebar.imageFallbackAlt");
                        return (
                          <div
                            key={attachment.id}
                            className="agent-image-attachment-preview"
                          >
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
                              aria-label={t("writing.aiSidebar.removeImage", { fileName })}
                              onClick={() => handleRemoveAttachment(attachment.id)}
                            >
                              <X size={12} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </PhotoProvider>
                ) : null}
                <AgentComposerEditor
                  projectId={projectId}
                  placeholder={getPlaceholder()}
                  value={value}
                  disabled={isComposerLocked}
                  onOpenMentionChapter={onOpenMentionChapter}
                  onMentionSuggestionsChange={setMentionSuggestions}
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
          justify="between"
          align="center"
          gap="2"
        >
          <Flex
            align="center"
            gap="2"
            wrap="wrap"
            style={{ flex: "1 1 auto", minWidth: 0 }}
          >
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
                  <Box
                    className="ai-sidebar-model-selector"
                    style={{ flex: "0 0 auto", minWidth: 0, marginRight: 4 }}
                  >
                    <SimpleSelect
                      value={agentKey ?? ""}
                      options={agentOptions}
                      onChange={onAgentChange}
                      size="1"
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
                  gap="2"
                  className="ai-sidebar-model-reasoning-group"
                >
                  <Box
                    className="ai-sidebar-model-selector"
                    style={{ flex: "0 1 auto", minWidth: 0 }}
                  >
                    <ModelIdSelect
                      value={modelId}
                      models={models}
                      onChange={onModelChange}
                      editable={false}
                      allowCustomValue={false}
                      compact
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
                    <Box className="ai-sidebar-reasoning-effort-selector">
                      <SimpleSelect
                        value={reasoningEffort}
                        options={reasoningEffortOptions}
                        onChange={(value) => onReasoningEffortChange(value as ReasoningEffort)}
                        size="1"
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
          >
            <AgentIndexStatusIndicator projectId={projectId} />

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
                  color: toolApprovalBypassEnabled ? "var(--green-11)" : "#111111",
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
