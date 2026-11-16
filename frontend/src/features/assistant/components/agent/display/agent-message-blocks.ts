import type {
  AgentChangeSummary,
  AgentMessage,
  AgentSessionChanges,
  AgentSessionStatus,
} from "@/lib/agent.types";

import {
  buildAgentDisplayItems,
  isAgentProcessMessage,
  type AgentDisplayItem,
} from "./agent-message-display-items";
import type {
  AgentBlockDisplayMessage,
  AgentOutputDisplayMessage,
  BlockDisplayMessage,
} from "./display-message-types";

export type AgentMessageBlockType = "user" | "agent" | "node";

export interface AgentMessageBlock {
  id: string;
  type: AgentMessageBlockType;
  messages: BlockDisplayMessage[];
  roundContent?: {
    blocks: AgentMessageBlock[];
    finalMessage?: AgentOutputDisplayMessage;
  };
  sourceRevisionId?: string;
  agentRoundId?: string;
  nodeId?: string;
  nodeStartedAt?: number;
  nodeEndedAt?: number;
  nodeElapsedBaseMs?: number;
  nodeStatus?: AgentMessage["status"];
  nodeEndStatus?: AgentMessage["status"];
}

export interface AgentRoundToolbarTarget {
  id: string;
  roundId: string;
  anchorBlockId: string;
  sourceRevisionId?: string;
  copyContent: string;
  timestamp?: number;
}

export interface AgentRoundProcess {
  id: string;
  anchorBlockId: string;
  finalMessageId: string | undefined;
  elapsedMs?: number;
  isActive: boolean;
  canCollapse: boolean;
}

export interface AgentDisplayItemPlacement {
  item: AgentDisplayItem;
  isClosed: boolean;
}

function isAgentBlockDisplayMessage(
  message: BlockDisplayMessage,
): message is AgentBlockDisplayMessage {
  return (
    message.type !== "user_request" && message.type !== "node_start" && message.type !== "node_end"
  );
}

export function buildAgentDisplayItemsByBlock(
  blocks: AgentMessageBlock[],
  processes: ReadonlyMap<string, AgentRoundProcess>,
): Map<string, AgentDisplayItemPlacement[]> {
  const rounds = new Map<string, AgentMessageBlock[]>();
  for (const block of blocks) {
    if (block.type !== "agent" || !block.agentRoundId) continue;
    const round = rounds.get(block.agentRoundId) ?? [];
    round.push(block);
    rounds.set(block.agentRoundId, round);
  }

  const placementsByBlock = new Map<string, AgentDisplayItemPlacement[]>();
  for (const [roundId, round] of rounds) {
    const agentBlocks = round.filter((block) => block.type === "agent");
    const messages = agentBlocks.flatMap((block) =>
      block.messages.filter(isAgentBlockDisplayMessage),
    );
    const items = buildAgentDisplayItems(messages);
    const process = processes.get(roundId);
    const blockIdByMessageId = new Map(
      agentBlocks.flatMap((block) =>
        block.messages
          .filter(isAgentBlockDisplayMessage)
          .map((message) => [message.id, block.id] as const),
      ),
    );

    items.forEach((item, index) => {
      const firstMessage = item.type === "process" ? item.messages[0] : item.message;
      if (!firstMessage) return;
      const blockId = blockIdByMessageId.get(firstMessage.id);
      if (!blockId) return;
      const placements = placementsByBlock.get(blockId) ?? [];
      placements.push({
        item,
        isClosed: item.type === "process" && (index < items.length - 1 || !process?.isActive),
      });
      placementsByBlock.set(blockId, placements);
    });
  }
  return placementsByBlock;
}

export function buildAgentRoundProcesses(
  blocks: AgentMessageBlock[],
  visibleBlocks: AgentMessageBlock[],
  isSessionActive: boolean,
  sessionStatus: AgentSessionStatus,
): Map<string, AgentRoundProcess> {
  const rounds = new Map<string, AgentMessageBlock[]>();
  for (const block of blocks) {
    if (!block.agentRoundId) continue;
    const round = rounds.get(block.agentRoundId) ?? [];
    round.push(block);
    rounds.set(block.agentRoundId, round);
  }
  const latestRoundId = Array.from(rounds.keys()).at(-1);
  const visibleBlockIds = new Set(visibleBlocks.map((block) => block.id));
  const processes = new Map<string, AgentRoundProcess>();
  for (const [roundId, round] of rounds) {
    const messages = round
      .filter((block) => block.type === "agent")
      .flatMap((block) => block.messages);
    const lastWork = messages.findLast(
      (message) =>
        isAgentProcessMessage(message) ||
        (message.type === "agent_output" && Boolean(message.content?.trim())),
    );
    const hasAnswer = lastWork?.type === "agent_output" && Boolean(lastWork.content?.trim());
    if (
      !messages.some(
        (message) =>
          isAgentProcessMessage(message) ||
          (message.type === "agent_output" &&
            Boolean(message.content?.trim()) &&
            message.id !== lastWork?.id),
      )
    )
      continue;
    const anchor = round.find((block) => visibleBlockIds.has(block.id) && block.type === "agent");
    if (!anchor) continue;
    const isActive = roundId === latestRoundId && isSessionActive;
    const isCompleted =
      roundId !== latestRoundId ||
      sessionStatus === "completed" ||
      (hasAnswer && lastWork.status === "completed") ||
      round.findLast((block) => block.type === "node")?.nodeEndStatus === "completed" ||
      messages.some((message) => message.type === "completed");
    const startedAt = round.find((block) => block.type === "user")?.messages[0]?.timestamp;
    const endTimes = [
      ...round
        .filter((block) => block.nodeEndStatus === "completed")
        .map((block) => block.nodeEndedAt),
      ...messages
        .filter((message) => message.type === "completed")
        .map((message) => message.timestamp),
    ].filter((time): time is number => time !== undefined && Number.isFinite(time));
    const endedAt = endTimes.length > 0 ? Math.max(...endTimes) : undefined;
    const elapsedMs =
      startedAt !== undefined &&
      Number.isFinite(startedAt) &&
      endedAt !== undefined &&
      endedAt >= startedAt &&
      endedAt >= (lastWork?.timestamp ?? startedAt)
        ? endedAt - startedAt
        : undefined;
    processes.set(roundId, {
      id: roundId,
      anchorBlockId: anchor.id,
      finalMessageId: lastWork?.type === "agent_output" ? lastWork.id : undefined,
      elapsedMs,
      isActive,
      canCollapse:
        Boolean(isCompleted && !isActive) &&
        !(roundId === latestRoundId && sessionStatus === "error") &&
        !round.some((block) => block.type === "node" && block.nodeStatus === "error") &&
        !messages.some(
          (message) =>
            message.type === "error" ||
            message.status === "running" ||
            message.status === "pending" ||
            message.isStreaming,
        ),
    });
  }
  return processes;
}

export function buildAgentRoundChangeSummaries(
  blocks: AgentMessageBlock[],
  visibleBlocks: AgentMessageBlock[],
  changes: AgentSessionChanges | null | undefined,
  isSessionRunning: boolean,
): Map<string, AgentChangeSummary> {
  const visibleBlockIds = new Set(visibleBlocks.map((block) => block.id));
  const rounds = new Map<
    string,
    { blocks: AgentMessageBlock[]; visibleBlocks: AgentMessageBlock[] }
  >();

  for (const block of blocks) {
    if (!block.agentRoundId) continue;
    let round = rounds.get(block.agentRoundId);
    if (!round) {
      round = { blocks: [], visibleBlocks: [] };
      rounds.set(block.agentRoundId, round);
    }
    round.blocks.push(block);
    if (visibleBlockIds.has(block.id)) round.visibleBlocks.push(block);
  }

  const summaries = new Map<string, AgentChangeSummary>();
  const lastRoundId = Array.from(rounds.keys()).at(-1);
  rounds.forEach((round, roundId) => {
    const agentBlocks = round.blocks.filter((block) => block.type === "agent");
    if (agentBlocks.length === 0 || agentBlocks.some(hasRunningAgentMessage)) return;
    if (isSessionRunning && roundId === lastRoundId) return;

    const anchorBlock = round.visibleBlocks.at(-1);
    if (!anchorBlock) return;

    const sourceRevisionId = agentBlocks.find((block) => block.sourceRevisionId)?.sourceRevisionId;
    const sourceUserMessageId = round.blocks.find((block) => block.type === "user")?.messages[0]
      ?.id;
    const summary = changes?.turns.find(
      (turn) =>
        (Boolean(sourceRevisionId) && turn.revisionId === sourceRevisionId) ||
        (Boolean(sourceUserMessageId) && turn.userMessageId === sourceUserMessageId),
    )?.changes;
    if (!summary || summary.itemCount === 0) return;
    summaries.set(anchorBlock.id, summary);
  });
  return summaries;
}

interface BuildAgentMessageBlocksOptions {
  closeOpenNodeAt?: number;
  previousBlocks?: AgentMessageBlock[];
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
  options: BuildAgentMessageBlocksOptions = {},
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
        activeNodeBlock.nodeEndStatus = undefined;
        continue;
      }
      if (resumableNodeBlock && nextNodeName && resumableNodeBlock.nodeName === nextNodeName) {
        activeNodeBlock = resumableNodeBlock.block;
        activeNodeId = resumableNodeBlock.nodeId;
        currentAgentBlock = resumableNodeBlock.agentBlock;
        activeNodeHasResumeBoundary = false;
        activeNodeBlock.nodeStartedAt = message.timestamp;
        activeNodeBlock.nodeEndedAt = undefined;
        activeNodeBlock.nodeEndStatus = undefined;
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
        activeNodeBlock.nodeStatus = isInterruptedNodeEndMessage(message)
          ? "error"
          : (message.status ?? activeNodeBlock.nodeStatus);
        activeNodeBlock.nodeEndStatus = activeNodeBlock.nodeStatus;
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
        agentRoundId: activeAgentRoundId,
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
    closeNodeSegment(
      activeNodeBlock,
      Math.max(activeNodeBlock.nodeStartedAt ?? options.closeOpenNodeAt, options.closeOpenNodeAt),
    );
    activeNodeBlock.nodeStatus = activeNodeBlock.nodeStatus === "error" ? "error" : "completed";
  }

  const previousIds = new Map(
    (options.previousBlocks ?? [])
      .filter((block) => block.type === "agent")
      .flatMap((block) => block.messages.map((message) => [message.id, block.id] as const)),
  );
  const usedIds = new Set<string>();
  for (const block of blocks) {
    if (block.type !== "agent") continue;
    const previousId = block.messages
      .map((message) => previousIds.get(message.id))
      .find((id) => id !== undefined && !usedIds.has(id));
    if (previousId) block.id = previousId;
    usedIds.add(block.id);
  }

  return blocks;
}

export function getVisibleAgentMessageBlocks(
  blocks: AgentMessageBlock[],
  collapsedNodeIds: ReadonlySet<string>,
): AgentMessageBlock[] {
  return blocks.filter((block) => {
    if (block.type === "node") return block.messages[0]?.display !== "hidden";
    return !block.nodeId || !collapsedNodeIds.has(block.nodeId);
  });
}

export function buildAgentRoundDisplayBlocks(
  blocks: AgentMessageBlock[],
  processes: ReadonlyMap<string, AgentRoundProcess>,
): AgentMessageBlock[] {
  const members = new Map<string, AgentMessageBlock[]>();
  for (const block of blocks) {
    if (block.type === "user" || !block.agentRoundId || !processes.get(block.agentRoundId))
      continue;
    const round = members.get(block.agentRoundId) ?? [];
    round.push(block);
    members.set(block.agentRoundId, round);
  }

  return blocks.flatMap((block) => {
    const process = block.agentRoundId ? processes.get(block.agentRoundId) : undefined;
    if (block.type === "user" || !block.agentRoundId || !process) return [block];
    if (block.id !== process.anchorBlockId) return [];
    const round = members.get(block.agentRoundId) ?? [];
    const messages = round.flatMap((member) => member.messages);
    const finalMessage = messages.find(
      (message): message is AgentOutputDisplayMessage =>
        message.type === "agent_output" && message.id === process.finalMessageId,
    );
    const processBlocks = round.flatMap((member) => {
      if (!finalMessage || !member.messages.some((message) => message.id === finalMessage.id))
        return [member];
      const messages = member.messages.filter((message) => message.id !== finalMessage?.id);
      return messages.length === 0 ? [] : [{ ...member, messages }];
    });
    return [{ ...block, messages, roundContent: { blocks: processBlocks, finalMessage } }];
  });
}

function hasRunningMessage(block: AgentMessageBlock): boolean {
  return block.messages.some((message) =>
    Boolean(message.isStreaming || message.status === "running"),
  );
}

function hasRunningAgentMessage(block: AgentMessageBlock): boolean {
  return (
    block.type === "agent" &&
    block.messages.some((message) =>
      Boolean(message.isStreaming || message.status === "running" || message.status === "pending"),
    )
  );
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
    if (
      message?.type === "agent_output" &&
      typeof message.timestamp === "number" &&
      Number.isFinite(message.timestamp)
    ) {
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
  visibleBlocks: AgentMessageBlock[],
  isSessionRunning: boolean,
): AgentRoundToolbarTarget[] {
  const roundOrder: string[] = [];
  const rounds = new Map<
    string,
    {
      blocks: AgentMessageBlock[];
      visibleBlocks: AgentMessageBlock[];
      sourceRevisionId?: string;
    }
  >();

  for (const block of blocks) {
    if (!block.agentRoundId) continue;
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

  return roundOrder.flatMap((roundId, index) => {
    const round = rounds.get(roundId);
    if (!round) return [];
    const hasAgentWork = round.blocks.some((block) => block.type === "agent");
    const isRunning = round.blocks.some(
      (block) => block.type === "agent" && hasRunningMessage(block),
    );
    const isLastRound = index === roundOrder.length - 1;
    const anchorBlock = round.visibleBlocks.at(-1);
    if (!hasAgentWork || isRunning || !anchorBlock) return [];
    if (isSessionRunning && isLastRound) return [];

    let copyContent = "";
    for (let index = round.blocks.length - 1; index >= 0; index -= 1) {
      const block = round.blocks[index];
      if (block?.type !== "agent") continue;
      copyContent = getLatestAssistantContentFromBlock(block);
      if (copyContent) break;
    }

    return [
      {
        id: `toolbar:${roundId}`,
        roundId,
        anchorBlockId: anchorBlock.id,
        sourceRevisionId: round.sourceRevisionId,
        copyContent,
        timestamp: getLatestAssistantToolbarTimestamp(round.blocks),
      },
    ];
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
