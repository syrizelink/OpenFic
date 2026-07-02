import { useEffect, useRef, useState } from "react";
import { Box, Text } from "@radix-ui/themes";
import { Brain } from "lucide-react";
import { useTranslation } from "react-i18next";

import { StreamingMarkdown } from "@/components";
import type { AgentMessage } from "@/lib/agent.types";
import { getReasoningDurationMs } from "../../../../../lib/streaming-message-merge";
import { formatElapsedDuration } from "../../shared/message-duration";
import {
  MessageBlockContent,
  MessageBlockHeader,
  MessageBlockHeaderMain,
  MessageBlockMeta,
  MessageBlockShell,
  MessageExpandButton,
} from "../../shared/message-shell";

import "./agent-thinking-message.css";

interface AgentThinkingMessageProps {
  message: AgentMessage;
}

const RUNNING_DURATION_TICK_MS = 100;

function getInitialDuration(message: AgentMessage): number {
  return getReasoningDurationMs(message);
}

export function AgentThinkingMessage({ message }: AgentThinkingMessageProps) {
  const { t } = useTranslation();
  const isRunning = Boolean(message.isStreaming || message.status === "running");
  const [initialDurationMs] = useState(() => getInitialDuration(message));
  const [startedAt] = useState(() => Date.now());
  const wasRunningRef = useRef(isRunning);
  const [durationMs, setDurationMs] = useState(initialDurationMs);
  const [isExpanded, setIsExpanded] = useState(isRunning);
  const content = message.content ?? "";
  const hasContent = content.trim().length > 0;

  useEffect(() => {
    if (!isRunning) return;

    const intervalId = window.setInterval(() => {
      setDurationMs(initialDurationMs + Date.now() - startedAt);
    }, RUNNING_DURATION_TICK_MS);

    return () => window.clearInterval(intervalId);
  }, [initialDurationMs, isRunning, startedAt]);

  useEffect(() => {
    if (isRunning) {
      wasRunningRef.current = true;
      queueMicrotask(() => setIsExpanded(true));
      return;
    }

    if (wasRunningRef.current) {
      wasRunningRef.current = false;
      queueMicrotask(() => {
        setDurationMs(initialDurationMs + Date.now() - startedAt);
        setIsExpanded(false);
      });
    }
  }, [initialDurationMs, isRunning, startedAt]);

  const handleToggleExpanded = () => {
    if (!hasContent) return;
    setIsExpanded((value) => !value);
  };

  return (
    <MessageBlockShell
      className="agent-reasoning-card"
      expandable={hasContent}
      flush
      isStreaming={isRunning}
      status={message.status ?? "completed"}
    >
      <MessageBlockHeader
        className="agent-reasoning-header"
        expandable={hasContent}
        expanded={isExpanded}
        onToggle={handleToggleExpanded}
      >
        <MessageBlockHeaderMain className="agent-reasoning-header-main">
          <Brain size={16} className="agent-message-shell-icon agent-reasoning-icon" />
          <Text
            size="1"
            weight="medium"
            className={isRunning ? "agent-message-shell-title agent-reasoning-title text-shimmer" : "agent-message-shell-title agent-reasoning-title"}
            data-text={t("assistant.thinkingTitle")}
          >
            {t("assistant.thinkingTitle")}
          </Text>
          <MessageBlockMeta className="agent-reasoning-meta">
            <Text size="1" color="gray" className="agent-message-shell-detail agent-reasoning-timer">
              {formatElapsedDuration(durationMs)}
            </Text>
            {hasContent ? (
              <MessageExpandButton
                className="agent-reasoning-expand-button"
                expanded={isExpanded}
                label={isExpanded ? t("assistant.collapseThinking") : t("assistant.expandThinking")}
              />
            ) : null}
          </MessageBlockMeta>
        </MessageBlockHeaderMain>
      </MessageBlockHeader>
      <MessageBlockContent
        contentClassName="agent-reasoning-content-shell"
        marginTop={8}
        motionKey="thinking-content"
        visible={hasContent && isExpanded}
      >
        <Box className="agent-tool-body agent-reasoning-body">
          <Box className="agent-tool-block-content agent-reasoning-content">
            <StreamingMarkdown
              content={content}
              isStreaming={isRunning}
              className="agent-markdown-content"
            />
          </Box>
        </Box>
      </MessageBlockContent>
    </MessageBlockShell>
  );
}
