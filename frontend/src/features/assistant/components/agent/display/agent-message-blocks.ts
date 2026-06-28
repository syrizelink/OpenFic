import type { AgentMessage } from "@/lib/agent.types";

import type { BlockDisplayMessage } from "./display-message-types";

export type AgentMessageBlockType = "user" | "agent" | "node";

export interface AgentMessageBlock {
  id: string;
  type: AgentMessageBlockType;
  messages: BlockDisplayMessage[];
  sourceRevisionId?: string;
  agentRoundId?: string;
  nodeId?: string;
  nodeStartedAt?: number;
  nodeEndedAt?: number;
  nodeElapsedBaseMs?: number;
  nodeStatus?: AgentMessage["status"];
}

export interface AgentRoundToolbarTarget {
  id: string;
  roundId: string;
  anchorBlockId: string;
  sourceRevisionId?: string;
  copyContent: string;
  timestamp?: number;
}

interface BuildAgentMessageBlocksOptions {
  closeOpenNodeAt?: number;
}

function isInterruptedNodeEndMessage(message: BlockDisplayMessage): boolean {
  if (message.type !== "node_end") return false;
  if (message.status === "error") return true;
  return message.payload?.status === "error";
}

function getNodeName(message: BlockDisplayMessage | undefined): string | undefined {
  if (!message) return undefined;
  const payloadNode = message.payload?.node;
  if (typeof payloadNode === "string" && payloadNode) return payloadNode;
  return message.agent;
}

function isNodeResumeBoundaryMessage(message: BlockDisplayMessage): boolean {
  return message.type === "tool" && message.toolName === "ask_user";
}

function closeNodeSegment(block: AgentMessageBlock, endedAt: number): void {
  const startedAt = block.nodeStartedAt ?? endedAt;
  block.nodeElapsedBaseMs = (block.nodeElapsedBaseMs ?? 0) + Math.max(0, endedAt - startedAt);
  block.nodeStartedAt = endedAt;
  block.nodeEndedAt = endedAt;
}

interface ResumableNodeBlock {
  nodeName: string;
  nodeId: string;
  block: AgentMessageBlock;
  agentBlock: AgentMessageBlock | null;
}

export function buildAgentMessageBlocks(
  messages: BlockDisplayMessage[],
  options: BuildAgentMessageBlocksOptions = {}
): AgentMessageBlock[] {
  const blocks: AgentMessageBlock[] = [];
  let pendingUserRevisionId: string | undefined;
  let currentAgentBlock: AgentMessageBlock | null = null;
  let activeNodeBlock: AgentMessageBlock | null = null;
  let activeNodeId: string | undefined;
  let activeNodeHasResumeBoundary = false;
  let resumableNodeBlock: ResumableNodeBlock | null = null;
  let activeAgentRoundId: string | undefined;
  let fallbackRoundCount = 0;

  const ensureAgentRoundId = () => {
    if (!activeAgentRoundId) {
      fallbackRoundCount += 1;
      activeAgentRoundId = `round:initial:${fallbackRoundCount}`;
    }
    return activeAgentRoundId;
  };

  for (const message of messages) {
    if (message.type === "node_start") {
      const activeNodeName = getNodeName(activeNodeBlock?.messages[0]);
      const nextNodeName = getNodeName(message);
      if (activeNodeBlock && activeNodeName && activeNodeName === nextNodeName) {
        activeNodeBlock.nodeStatus = message.status ?? activeNodeBlock.nodeStatus;
        activeNodeBlock.nodeEndedAt = undefined;
        continue;
      }
      if (resumableNodeBlock && nextNodeName && resumableNodeBlock.nodeName === nextNodeName) {
        activeNodeBlock = resumableNodeBlock.block;
        activeNodeId = resumableNodeBlock.nodeId;
        currentAgentBlock = resumableNodeBlock.agentBlock;
        activeNodeHasResumeBoundary = false;
        activeNodeBlock.nodeStartedAt = message.timestamp;
        activeNodeBlock.nodeEndedAt = undefined;
        activeNodeBlock.nodeStatus = message.status ?? activeNodeBlock.nodeStatus;
        resumableNodeBlock = null;
        continue;
      }
      resumableNodeBlock = null;
      currentAgentBlock = null;
      const agentRoundId = ensureAgentRoundId();
      activeNodeId = message.id;
      activeNodeHasResumeBoundary = false;
      activeNodeBlock = {
        id: `node:${message.id}`,
        type: "node",
        messages: [message],
        sourceRevisionId: pendingUserRevisionId,
        agentRoundId,
        nodeId: message.id,
        nodeStartedAt: message.timestamp,
        nodeStatus: message.status,
      };
      blocks.push(activeNodeBlock);
      continue;
    }

    if (message.type === "node_end") {
      if (activeNodeBlock) {
        closeNodeSegment(activeNodeBlock, message.timestamp);
        activeNodeBlock.nodeStatus = message.status ?? activeNodeBlock.nodeStatus;
        const nodeName = getNodeName(activeNodeBlock.messages[0]);
        const canResumeNode = activeNodeHasResumeBoundary || isInterruptedNodeEndMessage(message);
        if (canResumeNode && nodeName && activeNodeId) {
          resumableNodeBlock = {
            nodeName,
            nodeId: activeNodeId,
            block: activeNodeBlock,
            agentBlock: currentAgentBlock,
          };
        } else {
          resumableNodeBlock = null;
        }
      }
      currentAgentBlock = null;
      activeNodeBlock = null;
      activeNodeId = undefined;
      activeNodeHasResumeBoundary = false;
      continue;
    }

    if (message.type === "user_request") {
      if (activeNodeBlock) {
        closeNodeSegment(activeNodeBlock, message.timestamp);
        activeNodeBlock.nodeStatus = activeNodeBlock.nodeStatus === "error" ? "error" : "completed";
      }
      currentAgentBlock = null;
      activeNodeBlock = null;
      activeNodeId = undefined;
      activeNodeHasResumeBoundary = false;
      resumableNodeBlock = null;
      pendingUserRevisionId = message.revisionId;
      activeAgentRoundId = `round:${message.id}`;
      blocks.push({
        id: `user:${message.id}`,
        type: "user",
        messages: [message],
        sourceRevisionId: message.revisionId,
      });
      continue;
    }

    if (!currentAgentBlock) {
      const agentRoundId = ensureAgentRoundId();
      currentAgentBlock = {
        id: `agent:${message.id}`,
        type: "agent",
        messages: [],
        sourceRevisionId: pendingUserRevisionId,
        agentRoundId,
        nodeId: activeNodeId,
      };
      blocks.push(currentAgentBlock);
    }
    if (activeNodeBlock && isNodeResumeBoundaryMessage(message)) {
      activeNodeHasResumeBoundary = true;
    }
    currentAgentBlock.messages.push(message);
  }

  if (activeNodeBlock && typeof options.closeOpenNodeAt === "number") {
    closeNodeSegment(activeNodeBlock, Math.max(
      activeNodeBlock.nodeStartedAt ?? options.closeOpenNodeAt,
      options.closeOpenNodeAt
    ));
    activeNodeBlock.nodeStatus = activeNodeBlock.nodeStatus === "error" ? "error" : "completed";
  }

  return blocks;
}

export function getVisibleAgentMessageBlocks(
  blocks: AgentMessageBlock[],
  collapsedNodeIds: ReadonlySet<string>
): AgentMessageBlock[] {
  return blocks.filter((block) => {
    if (block.type === "node") return true;
    return !block.nodeId || !collapsedNodeIds.has(block.nodeId);
  });
}

function hasRunningMessage(block: AgentMessageBlock): boolean {
  return block.messages.some((message) => Boolean(message.isStreaming || message.status === "running"));
}

function getLatestRoundTimestamp(blocks: AgentMessageBlock[]): number | undefined {
  for (let blockIndex = blocks.length - 1; blockIndex >= 0; blockIndex -= 1) {
    const block = blocks[blockIndex];
    if (!block) continue;
    for (let messageIndex = block.messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
      const timestamp = block.messages[messageIndex]?.timestamp;
      if (typeof timestamp === "number" && Number.isFinite(timestamp)) return timestamp;
    }
  }
  return undefined;
}

function getLatestAssistantTimestampFromBlock(block: AgentMessageBlock): number | undefined {
  for (let index = block.messages.length - 1; index >= 0; index -= 1) {
    const message = block.messages[index];
    if (message?.type === "agent_output" && typeof message.timestamp === "number" && Number.isFinite(message.timestamp)) {
      return message.timestamp;
    }
  }
  return undefined;
}

function getLatestAssistantToolbarTimestamp(blocks: AgentMessageBlock[]): number | undefined {
  for (let blockIndex = blocks.length - 1; blockIndex >= 0; blockIndex -= 1) {
    const block = blocks[blockIndex];
    if (!block || block.type !== "agent") continue;
    const timestamp = getLatestAssistantTimestampFromBlock(block);
    if (typeof timestamp === "number") return timestamp;
  }
  return getLatestRoundTimestamp(blocks);
}

export function getAgentRoundToolbarTargets(
  blocks: AgentMessageBlock[],
  visibleBlocks: AgentMessageBlock[]
): AgentRoundToolbarTarget[] {
  const roundOrder: string[] = [];
  const rounds = new Map<string, {
    blocks: AgentMessageBlock[];
    visibleBlocks: AgentMessageBlock[];
    sourceRevisionId?: string;
  }>();

  for (const block of blocks) {
    if (!block.agentRoundId || (block.type !== "agent" && block.type !== "node")) continue;
    let round = rounds.get(block.agentRoundId);
    if (!round) {
      round = { blocks: [], visibleBlocks: [], sourceRevisionId: block.sourceRevisionId };
      rounds.set(block.agentRoundId, round);
      roundOrder.push(block.agentRoundId);
    }
    round.blocks.push(block);
    if (!round.sourceRevisionId && block.sourceRevisionId) {
      round.sourceRevisionId = block.sourceRevisionId;
    }
  }

  const visibleBlockIds = new Set(visibleBlocks.map((block) => block.id));
  for (const block of blocks) {
    if (!block.agentRoundId || !visibleBlockIds.has(block.id)) continue;
    const round = rounds.get(block.agentRoundId);
    if (round) round.visibleBlocks.push(block);
  }

  return roundOrder.flatMap((roundId) => {
    const round = rounds.get(roundId);
    if (!round) return [];
    const hasAgentWork = round.blocks.some((block) => block.type === "agent");
    const isRunning = round.blocks.some((block) => block.type === "agent" && hasRunningMessage(block));
    const anchorBlock = round.visibleBlocks.at(-1);
    if (!hasAgentWork || isRunning || !anchorBlock) return [];

    let copyContent = "";
    for (let index = round.blocks.length - 1; index >= 0; index -= 1) {
      const block = round.blocks[index];
      if (block?.type !== "agent") continue;
      copyContent = getLatestAssistantContentFromBlock(block);
      if (copyContent) break;
    }

    return [{
      id: `toolbar:${roundId}`,
      roundId,
      anchorBlockId: anchorBlock.id,
      sourceRevisionId: round.sourceRevisionId,
      copyContent,
      timestamp: getLatestAssistantToolbarTimestamp(round.blocks),
    }];
  });
}

export function getNodeElapsedMs(block: AgentMessageBlock, now = Date.now()): number {
  if (block.type !== "node") return 0;
  const elapsedBaseMs = block.nodeElapsedBaseMs ?? 0;
  if (typeof block.nodeStartedAt !== "number") return elapsedBaseMs;
  const end = typeof block.nodeEndedAt === "number" ? block.nodeEndedAt : now;
  return Math.max(0, elapsedBaseMs + end - block.nodeStartedAt);
}

export function getLatestAssistantContentFromBlock(block: AgentMessageBlock): string {
  for (let index = block.messages.length - 1; index >= 0; index -= 1) {
    const message = block.messages[index];
    if (message?.type === "agent_output" && message.content?.trim()) {
      return message.content.trim();
    }
  }
  return "";
}
