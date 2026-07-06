import { Box } from "@radix-ui/themes";
import { memo } from "react";

import { StreamingMarkdown } from "@/components";
import type { AgentMessage } from "@/lib/agent.types";

import { MessageCardShell } from "../../shared/message-shell";

interface AgentOutputMessageProps {
  message: AgentMessage;
}

function AgentOutputMessageView({ message }: AgentOutputMessageProps) {
  return (
    <MessageCardShell isStreaming={message.isStreaming || undefined}>
      {message.content ? (
        <Box className="agent-output-content">
          <StreamingMarkdown
            content={message.content}
            isStreaming={message.isStreaming}
            className="agent-markdown-content"
          />
        </Box>
      ) : null}
    </MessageCardShell>
  );
}

export const AgentOutputMessage = memo(AgentOutputMessageView);
