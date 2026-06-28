import { Flex, HoverCard, Text } from "@radix-ui/themes";
import { AlertCircle } from "lucide-react";

import type { AgentMessage } from "@/lib/agent.types";
import { MessageCardShell } from "../../shared/message-shell";

import "./status-message.css";

interface ErrorMessageProps {
  message: AgentMessage;
}

export function ErrorMessage({ message }: ErrorMessageProps) {
  const detail = message.content?.trim() || "暂无详细错误信息";

  return (
    <HoverCard.Root>
      <HoverCard.Trigger>
        <MessageCardShell className="agent-status-message-card">
          <Flex align="center" gap="2" className="agent-status-message-header">
            <AlertCircle size={16} className="agent-status-message-icon" data-status-tone="error" />
            <Text size="2" weight="medium" className="agent-status-message-title" data-status-tone="error">
              发生错误
            </Text>
          </Flex>
        </MessageCardShell>
      </HoverCard.Trigger>
      <HoverCard.Content side="bottom" align="start" size="2">
        <Text size="2" className="agent-status-message-detail" style={{ color: "var(--red-11)" }}>
          {detail}
        </Text>
      </HoverCard.Content>
    </HoverCard.Root>
  );
}
