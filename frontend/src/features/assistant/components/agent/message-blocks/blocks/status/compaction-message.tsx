import { Text } from "@radix-ui/themes";
import { ListChevronsDownUp } from "lucide-react";

import type { AgentMessage } from "@/lib/agent.types";

import "./status-message.css";

interface CompactionMessageProps {
  message: AgentMessage;
}

export function CompactionMessage({ message }: CompactionMessageProps) {
  const isRunning = message.status === "running";
  const content = isRunning ? "正在压缩上下文" : "上下文已压缩";
  const labelClassName = isRunning
    ? "agent-compaction-divider-label text-shimmer"
    : "agent-compaction-divider-label";

  return (
    <div className="agent-compaction-divider" data-status={message.status}>
      <span className="agent-compaction-divider-content">
        <ListChevronsDownUp size={14} className="agent-compaction-divider-icon" aria-hidden="true" />
        <Text
          as="span"
          size="1"
          weight="medium"
          className={labelClassName}
          data-text={isRunning ? content : undefined}
        >
          {content}
        </Text>
      </span>
    </div>
  );
}
