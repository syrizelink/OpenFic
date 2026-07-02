import NumberFlow from "@number-flow/react";
import { AnimatePresence, motion } from "motion/react";
import { memo, useState } from "react";
import { Box, Text } from "@radix-ui/themes";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  AgentBlockDisplayMessage,
} from "../../../display/display-message-types";
import type { ExplorationSummary } from "../../../display/agent-message-display-items";
import { AgentMessageRenderer } from "../../../agent-message-renderer";
import {
  MessageBlockContent,
  MessageBlockHeader,
  MessageBlockHeaderMain,
  MessageBlockMeta,
  MessageBlockShell,
  MessageExpandButton,
} from "../../shared/message-shell";

import "./exploration-message.css";

interface ExplorationMessageProps {
  messages: AgentBlockDisplayMessage[];
  summary: ExplorationSummary;
}

const SUMMARY_ITEMS = [
  { key: "chapterCount", labelKey: "assistant.explorationUnit.chapter" },
  { key: "listCount", labelKey: "assistant.explorationUnit.list" },
  { key: "contextCount", labelKey: "assistant.explorationUnit.context" },
  { key: "infoCount", labelKey: "assistant.explorationUnit.info" },
] as const;

function areExplorationSummariesEqual(prev: ExplorationSummary, next: ExplorationSummary) {
  return prev.chapterCount === next.chapterCount
    && prev.listCount === next.listCount
    && prev.contextCount === next.contextCount
    && prev.infoCount === next.infoCount;
}

function areExplorationMessagePropsEqual(
  prev: ExplorationMessageProps,
  next: ExplorationMessageProps
) {
  if (prev.messages === next.messages) {
    return areExplorationSummariesEqual(prev.summary, next.summary);
  }
  if (prev.messages.length !== next.messages.length) {
    return false;
  }
  for (let index = 0; index < prev.messages.length; index += 1) {
    if (prev.messages[index] !== next.messages[index]) {
      return false;
    }
  }
  return areExplorationSummariesEqual(prev.summary, next.summary);
}

function ExplorationMessageView({
  messages,
  summary,
}: ExplorationMessageProps) {
  const { t } = useTranslation();
  const isStreaming = messages.some((message) => Boolean(message.isStreaming || message.status === "running"));
  const hasContent = messages.length > 0;
  const [isExpanded, setIsExpanded] = useState(false);

  const summaryItems = SUMMARY_ITEMS.flatMap((item) => {
    const value = summary[item.key];
    if (value <= 0) return [];
    return [{
      key: item.key,
      value,
       label: t(item.labelKey),
    }];
  });

  const handleToggleExpanded = () => {
    if (!hasContent) return;
    setIsExpanded((value) => !value);
  };

  return (
    <MessageBlockShell
      className="agent-exploration-card"
      expandable={hasContent}
      flush
      isStreaming={isStreaming}
      status={isStreaming ? "running" : "completed"}
    >
      <MessageBlockHeader
        className="agent-exploration-header"
        expandable={hasContent}
        expanded={isExpanded}
        onToggle={handleToggleExpanded}
      >
        <MessageBlockHeaderMain className="agent-exploration-header-main">
          <Search size={16} className="agent-message-shell-icon agent-exploration-icon" />
          <Text
            size="1"
            weight="medium"
            className={isStreaming ? "agent-message-shell-title agent-exploration-title text-shimmer" : "agent-message-shell-title agent-exploration-title"}
            data-text={t("assistant.explorationTitle")}
          >
            {t("assistant.explorationTitle")}
          </Text>
          <MessageBlockMeta className="agent-exploration-meta">
            {summaryItems.length > 0 ? (
              <AnimatePresence initial={false} mode="popLayout">
                {summaryItems.map((item) => (
                  <motion.span
                    key={item.key}
                    layout
                    className="agent-exploration-summary-item"
                    initial={{ opacity: 0, width: 0, x: -4 }}
                    animate={{ opacity: 1, width: "auto", x: 0 }}
                    exit={{ opacity: 0, width: 0, x: -4 }}
                    transition={{
                      width: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
                      opacity: { duration: 0.14, ease: "easeOut" },
                      x: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
                    }}
                  >
                    <NumberFlow
                      value={item.value}
                      locales="zh-CN"
                      format={{ maximumFractionDigits: 0 }}
                      className="agent-exploration-summary-number"
                    />
                    <motion.span layout className="agent-exploration-summary-label">
                      {item.label}
                    </motion.span>
                  </motion.span>
                ))}
              </AnimatePresence>
            ) : null}
            {hasContent ? (
              <MessageExpandButton
                className="agent-exploration-expand-button"
                expanded={isExpanded}
                label={isExpanded ? t("assistant.collapseExploration") : t("assistant.expandExploration")}
              />
            ) : null}
          </MessageBlockMeta>
        </MessageBlockHeaderMain>
      </MessageBlockHeader>
      <MessageBlockContent
        keepMounted={hasContent}
        marginTop={0}
        motionKey="exploration-content"
        visible={hasContent && isExpanded}
      >
        <Box className="agent-exploration-content">
          {messages.map((message) => (
            <AgentMessageRenderer
              key={message.id}
              message={message}
            />
          ))}
        </Box>
      </MessageBlockContent>
    </MessageBlockShell>
  );
}

export const ExplorationMessage = memo(
  ExplorationMessageView,
  areExplorationMessagePropsEqual
);
