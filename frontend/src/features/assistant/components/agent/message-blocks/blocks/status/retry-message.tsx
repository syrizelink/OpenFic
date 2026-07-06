import { Flex, Text } from "@radix-ui/themes";
import { RotateCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AgentMessage } from "@/lib/agent.types";

import { MessageCardShell } from "../../shared/message-shell";

import "./status-message.css";

interface RetryMessageProps {
  message: AgentMessage;
}

function getRetryCount(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

export function RetryMessage({ message }: RetryMessageProps) {
  const { t } = useTranslation();
  const attempt = getRetryCount(message.payload?.attempt, 1);
  const maxAttempts = getRetryCount(message.payload?.max_attempts, attempt);
  const detail = message.content?.trim() || t("assistant.upstreamFailure");

  return (
    <MessageCardShell className="agent-status-message-card">
      <Flex
        direction="column"
        gap="1"
      >
        <Flex
          align="center"
          gap="2"
          className="agent-status-message-header"
        >
          <RotateCw
            size={16}
            className="agent-status-message-icon"
            data-status-tone="retry"
          />
          <Text
            size="2"
            weight="medium"
            className="agent-status-message-title"
            data-status-tone="retry"
          >
            {t("assistant.retryProgress", { attempt, max: maxAttempts })}
          </Text>
        </Flex>
        <Text
          size="1"
          color="gray"
          className="agent-status-message-detail"
        >
          {t("assistant.retryLastError", { detail })}
        </Text>
      </Flex>
    </MessageCardShell>
  );
}
