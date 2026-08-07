import { StreamingMarkdown } from "@/components";

import { VirtualizedMarkdownContent } from "./virtualized-message-content";

const VIRTUALIZE_CONTENT_THRESHOLD = 100_000;

interface AgentMarkdownContentProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
}

export function AgentMarkdownContent({
  content,
  isStreaming = false,
  className,
}: AgentMarkdownContentProps) {
  if (content.length > VIRTUALIZE_CONTENT_THRESHOLD) {
    return (
      <VirtualizedMarkdownContent
        content={content}
        isStreaming={isStreaming}
        className={className}
      />
    );
  }
  return (
    <StreamingMarkdown
      content={content}
      isStreaming={isStreaming}
      className={className}
    />
  );
}
