import { Flex, Text } from "@radix-ui/themes";
import { RotateCw } from "lucide-react";

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
  const attempt = getRetryCount(message.payload?.attempt, 1);
  const maxAttempts = getRetryCount(message.payload?.max_attempts, attempt);
  const detail = message.content?.trim() || "上游请求失败";

  return (
    <MessageCardShell className="agent-status-message-card">
      <Flex direction="column" gap="1">
        <Flex align="center" gap="2" className="agent-status-message-header">
          <RotateCw size={16} className="agent-status-message-icon" data-status-tone="retry" />
          <Text size="2" weight="medium" className="agent-status-message-title" data-status-tone="retry">
            {`正在重试（第 ${attempt} / ${maxAttempts} 次）`}
          </Text>
        </Flex>
        <Text size="1" color="gray" className="agent-status-message-detail">
          {`上次错误：${detail}`}
        </Text>
      </Flex>
    </MessageCardShell>
  );
}
