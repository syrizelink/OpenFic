import { Box, Text } from "@radix-ui/themes";
import {
  BookOpen,
  Brain,
  Bot,
  Globe,
  ListTodo,
  MessageCircleQuestionMark,
  PenLine,
  Search,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { AgentMessageRenderer } from "../../../agent-message-renderer";
import {
  getCompletedProcessActivity,
  getCompletedProcessTitle,
  getLiveProcessActivity,
  getLiveProcessTitleKey,
  type ProcessActivity,
} from "../../../display/agent-process-summary";
import type { AgentBlockDisplayMessage } from "../../../display/display-message-types";
import {
  MessageBlockContent,
  MessageBlockHeader,
  MessageBlockHeaderMain,
  MessageBlockMeta,
  MessageBlockShell,
  MessageExpandButton,
} from "../../shared/message-shell";

import "./process-message.css";

interface ProcessMessageProps {
  messages: AgentBlockDisplayMessage[];
  detailed: boolean;
  isClosed: boolean;
  isParentCollapsed: boolean;
  onAbortRetry?: () => void;
}

interface ProcessMessageHeaderProps {
  title: string;
  expanded: boolean;
  label: string;
  onToggle: () => void;
  isRunning?: boolean;
  activity?: ProcessActivity;
  showIcon?: boolean;
}

const PROCESS_ICONS: Record<ProcessActivity, LucideIcon> = {
  thinking: Brain,
  read: BookOpen,
  search: Search,
  edit: PenLine,
  webSearch: Globe,
  webFetch: BookOpen,
  subagents: Bot,
  skills: Sparkles,
  plan: ListTodo,
  questions: MessageCircleQuestionMark,
  tools: Wrench,
};

export function ProcessMessageHeader({
  title,
  expanded,
  label,
  onToggle,
  isRunning = false,
  activity = "thinking",
  showIcon = true,
}: ProcessMessageHeaderProps) {
  const Icon = PROCESS_ICONS[activity];
  return (
    <MessageBlockHeader
      className="agent-process-header"
      expandable
      expanded={expanded}
      onToggle={onToggle}
    >
      <MessageBlockHeaderMain className="agent-process-header-main">
        {showIcon ? (
          <Icon
            size={16}
            className="agent-message-shell-icon agent-process-icon"
          />
        ) : null}
        <Text
          size="1"
          weight="medium"
          className={
            isRunning
              ? "agent-message-shell-title agent-process-title text-shimmer"
              : "agent-message-shell-title agent-process-title"
          }
          data-text={title}
        >
          {title}
        </Text>
        <MessageBlockMeta className="agent-process-meta">
          <MessageExpandButton
            className="agent-process-expand-button"
            expanded={expanded}
            label={label}
          />
        </MessageBlockMeta>
      </MessageBlockHeaderMain>
    </MessageBlockHeader>
  );
}

export function ProcessMessage({
  messages,
  detailed,
  isClosed,
  isParentCollapsed,
  onAbortRetry,
}: ProcessMessageProps) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const isSubagentGroup = messages.some(
    (message) => message.type === "tool" && message.toolName === "dispatch_subagent",
  );
  useLayoutEffect(() => setIsExpanded(false), [detailed, isSubagentGroup, isParentCollapsed]);
  const isRunning = messages.some((message) =>
    Boolean(message.isStreaming || message.status === "running" || message.status === "pending"),
  );
  const hasError = messages.some((message) => message.status === "error");
  const liveTitleKey = getLiveProcessTitleKey(messages);
  const activity = isClosed
    ? getCompletedProcessActivity(messages)
    : getLiveProcessActivity(messages);
  const [displayedTitleKey, setDisplayedTitleKey] = useState(liveTitleKey);
  const titleChangedAt = useRef(Date.now());
  useEffect(() => {
    if (isClosed || displayedTitleKey === liveTitleKey) return;
    const timer = setTimeout(
      () => {
        setDisplayedTitleKey(liveTitleKey);
        titleChangedAt.current = Date.now();
      },
      Math.max(0, 150 - (Date.now() - titleChangedAt.current)),
    );
    return () => clearTimeout(timer);
  }, [displayedTitleKey, liveTitleKey, isClosed]);
  const title = isClosed ? getCompletedProcessTitle(messages, t) : t(displayedTitleKey);

  return (
    <MessageBlockShell
      className="agent-process-card"
      data-detailed={detailed}
      expandable={!detailed}
      flush
      isStreaming={isRunning}
      status={hasError ? "error" : isRunning ? "running" : "completed"}
    >
      {!detailed ? (
        <ProcessMessageHeader
          title={title}
          expanded={isExpanded}
          onToggle={() => setIsExpanded((value) => !value)}
          isRunning={!isClosed}
          activity={activity}
          label={
            isExpanded ? t("assistant.collapseProcessGroup") : t("assistant.expandProcessGroup")
          }
        />
      ) : null}
      <MessageBlockContent
        keepMounted
        marginTop={0}
        motionKey="process-content"
        visible={detailed || isExpanded}
      >
        <Box className="agent-process-content">
          {messages.map((message) => (
            <Box
              key={message.id}
              data-scroll-message-ids={JSON.stringify([message.id])}
            >
              <AgentMessageRenderer
                message={message}
                onAbortRetry={onAbortRetry}
              />
            </Box>
          ))}
        </Box>
      </MessageBlockContent>
    </MessageBlockShell>
  );
}
