import { memo } from "react";
import type { ComponentType } from "react";

import type { RenderableDisplayMessage } from "./display/display-message-types";
import { NodeStartMessage } from "./message-blocks/blocks/node/node-start-message";
import { AgentThinkingMessage } from "./message-blocks/blocks/reasoning/agent-thinking-message";
import { CompactionMessage } from "./message-blocks/blocks/status/compaction-message";
import { CompletedMessage } from "./message-blocks/blocks/status/completed-message";
import { ErrorMessage } from "./message-blocks/blocks/status/error-message";
import { RetryMessage } from "./message-blocks/blocks/status/retry-message";
import { AgentOutputMessage } from "./message-blocks/messages/special/agent-output-message";
import { ToolMessage } from "./message-blocks/messages/tool/tool-message";
import { UserRequestMessage } from "./message-blocks/messages/user/user-request-message";

interface AgentMessageRendererProps {
  message: RenderableDisplayMessage;
  nodeStartedAt?: number;
  nodeEndedAt?: number;
  nodeElapsedBaseMs?: number;
  isNodeCollapsed?: boolean;
  onToggleNode?: () => void;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
}

interface AgentMessageComponentProps {
  message: RenderableDisplayMessage;
}

const messageComponentMap: Partial<
  Record<RenderableDisplayMessage["type"], ComponentType<AgentMessageComponentProps>>
> = {
  reasoning: AgentThinkingMessage,
  retry: RetryMessage,
  compaction: CompactionMessage,
  completed: CompletedMessage,
  error: ErrorMessage,
  agent_output: AgentOutputMessage,
};

function AgentMessageRendererView({
  message,
  nodeStartedAt,
  nodeEndedAt,
  nodeElapsedBaseMs,
  isNodeCollapsed,
  onToggleNode,
  onOpenMentionChapter,
}: AgentMessageRendererProps) {
  if (message.type === "node_start") {
    return (
      <NodeStartMessage
        message={message}
        startedAt={nodeStartedAt}
        endedAt={nodeEndedAt}
        elapsedBaseMs={nodeElapsedBaseMs}
        isCollapsed={isNodeCollapsed}
        onToggle={onToggleNode}
      />
    );
  }

  if (message.type === "user_request") {
    return (
      <UserRequestMessage
        message={message}
        onOpenMentionChapter={onOpenMentionChapter}
      />
    );
  }

  if (message.type === "agent_output") {
    return <AgentOutputMessage message={message} />;
  }

  if (message.type === "tool") {
    return <ToolMessage message={message} />;
  }

  const MessageComponent = messageComponentMap[message.type];
  if (!MessageComponent) return null;

  return <MessageComponent message={message} />;
}

function areAgentMessageRendererPropsEqual(
  prev: AgentMessageRendererProps,
  next: AgentMessageRendererProps,
) {
  return (
    prev.message === next.message &&
    prev.nodeStartedAt === next.nodeStartedAt &&
    prev.nodeEndedAt === next.nodeEndedAt &&
    prev.nodeElapsedBaseMs === next.nodeElapsedBaseMs &&
    prev.isNodeCollapsed === next.isNodeCollapsed &&
    Boolean(prev.onToggleNode) === Boolean(next.onToggleNode) &&
    prev.onOpenMentionChapter === next.onOpenMentionChapter
  );
}

export const AgentMessageRenderer = memo(
  AgentMessageRendererView,
  areAgentMessageRendererPropsEqual,
);
