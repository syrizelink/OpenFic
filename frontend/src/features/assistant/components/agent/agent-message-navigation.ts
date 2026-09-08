import type { AgentMessageBlock } from "./display/agent-message-blocks";

export interface AgentMessageNavigationItem {
  id: string;
  blockIndex: number;
  preview: string;
  timestamp?: number;
}

const PREVIEW_LENGTH = 100;

function createPreview(content: string | undefined, emptyPreview: string): string {
  const text = (content ?? "")
    .replace(/<[^>]+>/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[`*_>#~-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!text) return emptyPreview;
  return text.length > PREVIEW_LENGTH ? `${text.slice(0, PREVIEW_LENGTH)}…` : text;
}

export function buildAgentMessageNavigationItems(
  blocks: AgentMessageBlock[],
  emptyPreview: string,
): AgentMessageNavigationItem[] {
  return blocks.flatMap((block, blockIndex) => {
    if (block.type !== "user") return [];
    const message = block.messages[0];
    if (!message || message.type !== "user_request") return [];

    return [
      {
        id: block.id,
        blockIndex,
        preview: createPreview(message.content, emptyPreview),
        timestamp: Number.isFinite(message.timestamp) ? message.timestamp : undefined,
      },
    ];
  });
}

export function getActiveAgentMessageNavigationId(
  items: AgentMessageNavigationItem[],
  visibleStartIndex: number,
): string | null {
  if (items.length === 0) return null;

  let active = items[0];
  for (const item of items) {
    if (item.blockIndex > visibleStartIndex) break;
    active = item;
  }
  return active.id;
}
