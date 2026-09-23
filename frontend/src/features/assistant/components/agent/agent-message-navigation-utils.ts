interface MessageNavigationMessage {
  id?: string;
  type: string;
  content?: string | null;
}

interface MessageNavigationBlock {
  id: string;
  type: "user" | "agent" | "node";
  agentRoundId?: string;
  messages: readonly MessageNavigationMessage[];
}

export interface AgentMessageNavigationItem {
  id: string;
  blockIndex: number;
  userMessageId: string;
  userContent: string;
  assistantContent: string;
}

function getAssistantContent(
  blocks: readonly MessageNavigationBlock[],
  userBlock: MessageNavigationBlock,
  userBlockIndex: number,
): string {
  const assistantBlocks = userBlock.agentRoundId
    ? blocks.filter(
        (block) => block.type === "agent" && block.agentRoundId === userBlock.agentRoundId,
      )
    : blocks.slice(userBlockIndex + 1).filter((block) => block.type === "agent");

  return assistantBlocks
    .flatMap((block) => block.messages)
    .filter((message) => message.type === "agent_output" && message.content?.trim())
    .map((message) => message.content?.trim() ?? "")
    .join("\n\n");
}

export function buildAgentMessageNavigationItems(
  blocks: readonly MessageNavigationBlock[],
  indexedBlocks: readonly MessageNavigationBlock[] = blocks,
): AgentMessageNavigationItem[] {
  return blocks.flatMap((block, blockIndex) => {
    if (block.type !== "user") return [];
    const userMessage = block.messages[0];
    const indexedBlockIndex = indexedBlocks.findIndex((item) => item.id === block.id);
    if (indexedBlockIndex < 0) return [];
    return [
      {
        id: block.id,
        blockIndex: indexedBlockIndex,
        userMessageId: userMessage?.id ?? block.id,
        userContent: userMessage?.content ?? "",
        assistantContent: getAssistantContent(blocks, block, blockIndex),
      },
    ];
  });
}

export function getActiveMessageNavigationIndex(
  userBlockIndices: readonly number[],
  visibleBlockIndex: number,
): number {
  if (userBlockIndices.length === 0) return -1;

  let low = 0;
  let high = userBlockIndices.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (userBlockIndices[middle] <= visibleBlockIndex) low = middle + 1;
    else high = middle;
  }

  return Math.max(0, low - 1);
}

export function getMessageNavigationNeighborCount(itemCount: number): 0 | 1 | 2 | 3 {
  return itemCount >= 8 ? 3 : itemCount >= 6 ? 2 : itemCount >= 4 ? 1 : 0;
}

export function getMessageNavigationNeighborDistance(
  itemIndex: number,
  hoveredIndex: number | null,
  itemCount: number,
): 0 | 1 | 2 | 3 {
  if (hoveredIndex === null) return 0;
  const maxNeighborDistance = getMessageNavigationNeighborCount(itemCount);
  const distance = Math.abs(itemIndex - hoveredIndex);
  if (distance === 0 || distance > maxNeighborDistance) return 0;
  return distance as 1 | 2 | 3;
}

export function getMessageNavigationNeighborScale(
  distance: 1 | 2 | 3,
  neighborCount: number,
): number {
  if (neighborCount === 1) return 1.75;
  if (neighborCount === 2) return distance === 1 ? 1.75 : 1.375;
  if (neighborCount === 3) {
    if (distance === 1) return 1.75;
    if (distance === 2) return 1.5;
    return 1.25;
  }
  return 1;
}

export function getMessageNavigationScrollState(
  scrollTop: number,
  clientHeight: number,
  scrollHeight: number,
): { canScrollUp: boolean; canScrollDown: boolean } {
  const scrollEpsilon = 1;
  return {
    canScrollUp: scrollTop > scrollEpsilon,
    canScrollDown: scrollTop + clientHeight < scrollHeight - scrollEpsilon,
  };
}
