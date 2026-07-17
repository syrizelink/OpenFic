import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { ArrowUp, CircleUserRound, ExternalLink, ShieldCheck, Square } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ModelIdSelect, Spinner, type ModelIdSelectOption } from "@/components";
import { SimpleSelect, type SelectOption } from "@/components/select";
import { ProviderIcon } from "@/features/settings/lib/provider-icons";
import type { AgentPendingMessage, AgentSessionStatus, ReasoningEffort } from "@/lib/agent.types";

import { AgentComposerEditor, type AgentComposerSuggestionState } from "./agent-composer-editor";
import { AgentIndexStatusIndicator } from "./agent-index-status-indicator";
import { canSendAgentInput, getAgentInputBodyMode, isAgentInputLocked } from "./agent-input-state";
import { AgentMentionSuggestions } from "./agent-mention-suggestions";
import { AgentPendingMessageCard } from "./pending-message-card";

interface AgentInputProps {
  projectId: string;
  value: string;
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
  [ignoredModeSelectorProp: string]: unknown;
}

export function AgentInput({
  projectId,
  value,
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
}: AgentInputProps) {
  const { t } = useTranslation();
  const bodyMode = getAgentInputBodyMode(agentStatus, Boolean(specialPanels), forceSpecialPanels);
  const hasContent = value.trim().length > 0;
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
  const selectedModel = useMemo(
    () => models.find((model) => model.value === modelId || model.id === modelId),
    [modelId, models],
  );
  const modelTriggerPrefix = selectedModel ? (
    <ProviderIcon
      size={14}
      iconPath={selectedModel.providerIconPath}
    />
  ) : null;
  const shouldShowReasoningEffort = selectedModel?.reasoning === true;
  const reasoningEffortOptions: SelectOption[] = [
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "xhigh", label: "Xhigh" },
    { value: "max", label: "Max" },
  ];

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

  const getPlaceholder = () => {
    if (agentStatus === "waiting_answer")
      return t("writing.aiSidebar.inputPlaceholderWaitingAnswer");
    if (agentStatus === "waiting_approval")
      return t("writing.aiSidebar.inputPlaceholderWaitingApproval");
    return t("writing.aiSidebar.inputPlaceholder");
  };

  return (
    <Box className="ai-sidebar-input-area">
      <motion.div
        layout
        className="ai-sidebar-input-stage"
        transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      >
        <AnimatePresence initial={false}>
          {mentionSuggestions ? (
            <AgentMentionSuggestions
              key="mention-suggestions"
              clearanceHeight={pendingClearanceHeight}
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

        <motion.div
          ref={inputContainerRef}
          layout
          className="ai-sidebar-input-container"
          data-mode={bodyMode}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
        >
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
                    fontSize: "12px",
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
                <AgentComposerEditor
                  projectId={projectId}
                  placeholder={getPlaceholder()}
                  value={value}
                  disabled={isComposerLocked}
                  onOpenMentionChapter={onOpenMentionChapter}
                  onMentionSuggestionsChange={setMentionSuggestions}
                  onChange={onChange}
                  onSubmit={onSend}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>

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
                      triggerPrefix={
                        <CircleUserRound
                          size={14}
                          aria-hidden="true"
                        />
                      }
                      hideTriggerChevron
                      triggerClassName="ai-sidebar-inline-select-trigger ai-sidebar-agent-select-trigger"
                      triggerStyle={{
                        fontSize: "12px",
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
                        fontSize: "12px",
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
                          fontSize: "12px",
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
                onClick={shouldAbort ? onAbort : onSend}
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
