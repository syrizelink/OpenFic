import { Box, Flex, Text } from "@radix-ui/themes";
import { CheckCircle } from "lucide-react";

import type { AgentMessage } from "@/lib/agent.types";
import { MessageCardShell } from "../../shared/message-shell";

import "./status-message.css";

interface CompletedMessageProps {
  message: AgentMessage;
}

export function CompletedMessage({ message }: CompletedMessageProps) {
  return (
    <MessageCardShell className="agent-status-message-card">
      <Flex align="center" gap="2" mb="3" className="agent-status-message-header">
        <CheckCircle size={16} className="agent-status-message-icon" data-status-tone="completed" />
        <Text size="2" weight="medium" className="agent-status-message-title" data-status-tone="completed">
          内容创作完成
        </Text>
      </Flex>
      <Box>
        {message.wordCount !== undefined ? (
          <Text size="2" className="agent-status-message-summary">
            共生成 {message.wordCount} 字
            {message.iteration !== undefined && message.iteration > 1 ? (
              <Text as="span" size="2" className="agent-status-message-summary-note">
                ，经过 {message.iteration} 次迭代优化
              </Text>
            ) : null}
          </Text>
        ) : null}
      </Box>
    </MessageCardShell>
  );
}
